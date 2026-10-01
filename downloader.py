import gc
import time
from datetime import timedelta
from concurrent.futures import ProcessPoolExecutor
import numpy as np
import xarray as xr
from meteodatalab import ogd_api, grib_decoder, data_source
import config

def safe_squeeze(ds):
    """Entfernt nur 1er-Dimensionen von ref_time, z und eps – NIEMALS lead_time!"""
    drop_dims = [d for d in ['ref_time', 'z'] if d in ds.dims and ds.sizes[d] == 1]
    if 'eps' in ds.dims and ds.sizes['eps'] == 1:
        drop_dims.append('eps')
    return ds.squeeze(drop_dims) if drop_dims else ds

def get_hhl(valid_cells=None):
    """Lädt die statische Geometrie (Höhe der Schichtgrenzen HHL) einmalig."""
    print("-> Lade statische vertikale Gittergeometrie (HHL)...", flush=True)
    url_ch1_vert = ogd_api.get_collection_asset_url(
        collection_id="ch.meteoschweiz.ogd-forecasting-icon-ch1",
        asset_id="vertical_constants_icon-ch1-eps.grib2"
    )
    ds_vert = grib_decoder.load(
        source=data_source.URLDataSource(urls=[url_ch1_vert]),
        request={"param": "HHL"},
        geo_coords=lambda uuid: {}
    )
    hhl = ds_vert["HHL"]
    if valid_cells is not None:
        hhl = hhl.isel(cell=valid_cells)
    return hhl.values  # Shape: (81, num_cells)

def interpolate_3d_to_altitude(da_3d, hhl_values, target_alt=config.TARGET_ALTITUDE):
    """
    Interpoliert ein 3D-Feld (z, cell) oder (lead_time/eps, z, cell) linear auf target_alt.
    Punkte, an denen das Gelände > target_alt liegt, werden auf NaN gesetzt.
    """
    # Schichthöhen der Vollschichten (Mittelwert der Halbschichten)
    h_full = 0.5 * (hhl_values[:-1, :] + hhl_values[1:, :])  # Shape: (80, num_cells)
    hsurf = hhl_values[-1, :]  # Gelände-Oberfläche

    # Finde die Schichtgrenzen k und k+1 (h_full fällt mit steigendem Index von 22km auf Boden)
    is_below = h_full < target_alt
    idx_below = np.argmax(is_below, axis=0)
    idx_above = np.maximum(0, idx_below - 1)

    num_cells = hhl_values.shape[1]
    col_idx = np.arange(num_cells)

    h_a = h_full[idx_above, col_idx]
    h_b = h_full[idx_below, col_idx]
    dh = np.where((h_a - h_b) == 0, 1e-6, h_a - h_b)
    weight = (target_alt - h_b) / dh

    # Geländemaskierung: alles über 1500m ist Fels
    mask_underground = (hsurf >= target_alt) | (~np.any(is_below, axis=0))

    # Dimensions-Handling für Xarray (z-Dimension finden)
    z_dim = [d for d in da_3d.dims if d in ['generalVerticalLayer', 'z', 'level']][0]
    z_axis = da_3d.dims.index(z_dim)

    vals = da_3d.values
    # Bringt z-Dimension nach vorne für sauberes Slicing
    vals_trans = np.moveaxis(vals, z_axis, 0)
    
    val_above = vals_trans[idx_above, ..., col_idx]
    val_below = vals_trans[idx_below, ..., col_idx]
    
    val_interp = (1.0 - weight) * val_below + weight * val_above
    val_interp[..., mask_underground] = np.nan

    # Erzeuge 2D-DataArray ohne Z-Dimension zurück
    new_dims = [d for d in da_3d.dims if d != z_dim]
    coords = {c: da_3d.coords[c] for c in new_dims if c in da_3d.coords}
    return xr.DataArray(val_interp, dims=new_dims, coords=coords)

def _download_and_crop_task(args):
    var_name, perturbed, ref_time_str, lead_times, valid_cells, hhl_values = args
    label = f"{var_name} ({'Ensemble' if perturbed else 'Hauptlauf'})"
    
    req = ogd_api.Request(
        collection="ogd-forecasting-icon-ch1",
        variable=var_name,
        ref_time=ref_time_str,
        perturbed=perturbed,
        lead_time=lead_times
    )
    
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            print(f"-> [Worker] Starte Download für {label} (Versuch {attempt}/{max_retries})...", flush=True)
            ds = ogd_api.get_from_ogd(req)
            if valid_cells is not None:
                ds = ds.isel(cell=valid_cells)
            ds = safe_squeeze(ds)

            # Wenn es eine 3D-Höhenvariable ist, sofort vertikal schneiden
            if var_name in ["U", "V"]:
                ds = interpolate_3d_to_altitude(ds, hhl_values, config.TARGET_ALTITUDE)

            print(f"✓ [Worker] Fertig & verarbeitet: {label}", flush=True)
            return ds
        except Exception as e:
            print(f"⚠️ Warnung bei {label} (Versuch {attempt}): {e}", flush=True)
            if attempt == max_retries:
                raise e
            time.sleep(3 * attempt)

def fetch_weather_data(start_step, end_step, ref_time_str):
    lead_times = [timedelta(hours=h) for h in range(start_step, end_step + 1)]

    print(f"1. Pilot-Download: Hole Hauptlauf U_10M für Schritte {start_step} bis {end_step}...", flush=True)
    req_pilot = ogd_api.Request(
        collection="ogd-forecasting-icon-ch1",
        variable="U_10M",
        ref_time=ref_time_str,
        perturbed=False,
        lead_time=lead_times
    )

    for attempt in range(1, 4):
        try:
            ds_u_h_raw = ogd_api.get_from_ogd(req_pilot)
            break
        except Exception as e:
            if attempt == 3:
                raise e
            time.sleep(3)

    # Gittermaske der Schweiz berechnen
    lats = ds_u_h_raw.coords['lat'].values
    lons = ds_u_h_raw.coords['lon'].values
    valid_cells = np.where(
        (lats >= config.LAT_MIN) & (lats <= config.LAT_MAX) & 
        (lons >= config.LON_MIN) & (lons <= config.LON_MAX)
    )[0]

    u_h = safe_squeeze(ds_u_h_raw.isel(cell=valid_cells))
    del ds_u_h_raw
    gc.collect()

    # Statisches Vertikalgitter HHL laden
    hhl_values = get_hhl(valid_cells)

    print("2. Starte parallelen Download (10m & 1500m Wind)...", flush=True)
    tasks = [
        ("V_10M", False, ref_time_str, lead_times, valid_cells, None),
        ("VMAX_10M", False, ref_time_str, lead_times, valid_cells, None),
        ("U_10M", True, ref_time_str, lead_times, valid_cells, None),
        ("V_10M", True, ref_time_str, lead_times, valid_cells, None),
        ("VMAX_10M", True, ref_time_str, lead_times, valid_cells, None),
        ("U", False, ref_time_str, lead_times, valid_cells, hhl_values),
        ("V", False, ref_time_str, lead_times, valid_cells, hhl_values),
        ("U", True, ref_time_str, lead_times, valid_cells, hhl_values),
        ("V", True, ref_time_str, lead_times, valid_cells, hhl_values)
    ]

    with ProcessPoolExecutor(max_workers=2) as executor:
        v_h, g_h, u_e, v_e, g_e, u15_h, v15_h, u15_e, v15_e = list(executor.map(_download_and_crop_task, tasks))

    print("✓ Alle 10 Wetter-Datensätze erfolgreich empfangen!", flush=True)
    del hhl_values
    gc.collect()

    return u_h, v_h, g_h, u_e, v_e, g_e, u15_h, v15_h, u15_e, v15_e

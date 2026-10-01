import os
import gc
import time
from datetime import timedelta
import numpy as np
import xarray as xr
from meteodatalab import ogd_api, grib_decoder, data_source
import config

class SilenceStderr:
    """Schaltet C-Level Meldungen (z.B. ecCodes Versions-Warnungen) zuverlässig stumm."""
    def __enter__(self):
        try:
            self.null_fd = os.open(os.devnull, os.O_RDWR)
            self.save_fd = os.dup(2)
            os.dup2(self.null_fd, 2)
        except Exception:
            self.null_fd = None

    def __exit__(self, *_):
        if self.null_fd is not None:
            try:
                os.dup2(self.save_fd, 2)
                os.close(self.null_fd)
                os.close(self.save_fd)
            except Exception:
                pass

def safe_squeeze(ds):
    """Entfernt nur 1er-Dimensionen von ref_time und eps – lead_time und vertikale Achsen bleiben erhalten."""
    drop_dims = [d for d in ['ref_time', 'eps'] if d in ds.dims and ds.sizes[d] == 1]
    return ds.squeeze(drop_dims) if drop_dims else ds

def get_hhl(valid_cells=None):
    """Lädt die statische Geometrie (HHL) und bringt sie garantiert auf Shape (81, cells)."""
    print("-> Lade statische vertikale Gittergeometrie (HHL)...", flush=True)
    url_ch1_vert = ogd_api.get_collection_asset_url(
        collection_id="ch.meteoschweiz.ogd-forecasting-icon-ch1",
        asset_id="vertical_constants_icon-ch1-eps.grib2"
    )
    with SilenceStderr():
        ds_vert = grib_decoder.load(
            source=data_source.URLDataSource(urls=[url_ch1_vert]),
            request={"param": "HHL"},
            geo_coords=lambda uuid: {}
        )
    hhl_da = ds_vert["HHL"]
    
    # Alle Dummy-Dimensionen (wie eps=1, ref_time=1) entfernen
    hhl_da = hhl_da.squeeze()

    if valid_cells is not None:
        hhl_da = hhl_da.isel(cell=valid_cells)
    
    vals = hhl_da.values
    # Sicherstellen, dass die vertikale Achse (81 Schichten) an Achse 0 liegt
    if vals.shape[0] != 81 and vals.shape[-1] == 81:
        vals = np.moveaxis(vals, -1, 0)
    
    print(f"✓ HHL geladen mit Form: {vals.shape} (81 Schichtgrenzen)", flush=True)
    return vals

def interpolate_3d_to_altitude(da_3d, hhl_values, target_alt=config.TARGET_ALTITUDE):
    """
    Interpoliert ein 3D-Windfeld linear auf target_alt (1500m ü. M.).
    Gitterpunkte mit Gelände >= target_alt werden auf NaN gesetzt.
    """
    # Schichthöhen der 80 Vollschichten (Mittelwert der 81 Schichtgrenzen)
    h_full = 0.5 * (hhl_values[:-1, :] + hhl_values[1:, :])  # Shape: (80, num_cells)
    hsurf = hhl_values[-1, :]  # Geländeoberkante (unterste Schichtgrenze)

    num_cells = hhl_values.shape[1]
    col_idx = np.arange(num_cells)

    # In ICON fällt h_full von Level 0 (~22km) bis Level 79 (Boden)
    is_below = (h_full < target_alt)
    
    # idx_below: Erste Schicht von oben, die unter target_alt liegt
    idx_below = np.argmax(is_below, axis=0)
    idx_above = np.maximum(0, idx_below - 1)

    h_a = h_full[idx_above, col_idx]
    h_b = h_full[idx_below, col_idx]
    dh = np.where((h_a - h_b) == 0, 1e-6, h_a - h_b)
    weight = np.clip((target_alt - h_b) / dh, 0.0, 1.0)

    # Untergrund-Maskierung (Bergmassiv / Fels über 1500m)
    mask_underground = (hsurf >= target_alt) | (~np.any(is_below, axis=0))

    # Finde vertikale Dimension im 3D Datensatz
    z_dim = [d for d in da_3d.dims if d in ['generalVerticalLayer', 'z', 'level']][0]
    z_axis = da_3d.dims.index(z_dim)

    vals = da_3d.values
    vals_trans = np.moveaxis(vals, z_axis, 0)

    val_above = vals_trans[idx_above, ..., col_idx]
    val_below = vals_trans[idx_below, ..., col_idx]

    val_interp = (1.0 - weight) * val_below + weight * val_above
    val_interp[..., mask_underground] = np.nan

    new_dims = [d for d in da_3d.dims if d != z_dim]
    coords = {c: da_3d.coords[c] for c in new_dims if c in da_3d.coords}
    return xr.DataArray(val_interp, dims=new_dims, coords=coords)

def fetch_single_2d(var_name, perturbed, ref_time_str, lead_times, valid_cells):
    req = ogd_api.Request(
        collection="ogd-forecasting-icon-ch1",
        variable=var_name,
        ref_time=ref_time_str,
        perturbed=perturbed,
        lead_time=lead_times
    )
    with SilenceStderr():
        ds = ogd_api.get_from_ogd(req)
    if valid_cells is not None:
        ds = ds.isel(cell=valid_cells)
    return safe_squeeze(ds)

def fetch_3d_and_slice(var_name, perturbed, ref_time_str, lead_times, valid_cells, hhl_values):
    label = f"{var_name} 1500m ({'Ensemble' if perturbed else 'Hauptlauf'})"
    print(f"-> Verarbeite {label} stufenweise für {len(lead_times)} Zeitschritte...", flush=True)
    
    hourly_slices = []
    for lt in lead_times:
        req = ogd_api.Request(
            collection="ogd-forecasting-icon-ch1",
            variable=var_name,
            ref_time=ref_time_str,
            perturbed=perturbed,
            lead_time=[lt]
        )
        with SilenceStderr():
            ds_hour = ogd_api.get_from_ogd(req)
        
        if valid_cells is not None:
            ds_hour = ds_hour.isel(cell=valid_cells)
        ds_hour = safe_squeeze(ds_hour)

        ds_1500 = interpolate_3d_to_altitude(ds_hour, hhl_values, config.TARGET_ALTITUDE)
        hourly_slices.append(ds_1500)
        
        del ds_hour
        gc.collect()

    if len(hourly_slices) > 1:
        return xr.concat(hourly_slices, dim="lead_time")
    return hourly_slices[0]

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

    with SilenceStderr():
        ds_u_h_raw = ogd_api.get_from_ogd(req_pilot)

    lats = ds_u_h_raw.coords['lat'].values
    lons = ds_u_h_raw.coords['lon'].values
    valid_cells = np.where(
        (lats >= config.LAT_MIN) & (lats <= config.LAT_MAX) & 
        (lons >= config.LON_MIN) & (lons <= config.LON_MAX)
    )[0]

    u_h = safe_squeeze(ds_u_h_raw.isel(cell=valid_cells))
    del ds_u_h_raw
    gc.collect()

    print("2. Lade 10m Wind & Böen Felder...", flush=True)
    v_h = fetch_single_2d("V_10M", False, ref_time_str, lead_times, valid_cells)
    g_h = fetch_single_2d("VMAX_10M", False, ref_time_str, lead_times, valid_cells)
    u_e = fetch_single_2d("U_10M", True, ref_time_str, lead_times, valid_cells)
    v_e = fetch_single_2d("V_10M", True, ref_time_str, lead_times, valid_cells)
    g_e = fetch_single_2d("VMAX_10M", True, ref_time_str, lead_times, valid_cells)

    print("3. Lade vertikales Höhenprofil & berechne 1500m Wind...", flush=True)
    hhl_values = get_hhl(valid_cells)

    u15_h = fetch_3d_and_slice("U", False, ref_time_str, lead_times, valid_cells, hhl_values)
    v15_h = fetch_3d_and_slice("V", False, ref_time_str, lead_times, valid_cells, hhl_values)
    u15_e = fetch_3d_and_slice("U", True, ref_time_str, lead_times, valid_cells, hhl_values)
    v15_e = fetch_3d_and_slice("V", True, ref_time_str, lead_times, valid_cells, hhl_values)

    del hhl_values
    gc.collect()

    print("✓ Alle 10 Datensätze speicherschonend im RAM bereitgestellt!", flush=True)
    return u_h, v_h, g_h, u_e, v_e, g_e, u15_h, v15_h, u15_e, v15_e

import os
import gc
import time
import threading
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import xarray as xr
from meteodatalab import ogd_api, grib_decoder, data_source
import config

class SilenceStderr:
    _lock = threading.Lock()
    _refcount = 0
    _save_fd = None
    _null_fd = None

    def __enter__(self):
        with SilenceStderr._lock:
            if SilenceStderr._refcount == 0:
                try:
                    SilenceStderr._null_fd = os.open(os.devnull, os.O_RDWR)
                    SilenceStderr._save_fd = os.dup(2)
                    os.dup2(SilenceStderr._null_fd, 2)
                except Exception:
                    pass
            SilenceStderr._refcount += 1

    def __exit__(self, *_):
        with SilenceStderr._lock:
            SilenceStderr._refcount -= 1
            if SilenceStderr._refcount == 0 and SilenceStderr._save_fd is not None:
                try:
                    os.dup2(SilenceStderr._save_fd, 2)
                    os.close(SilenceStderr._null_fd)
                    os.close(SilenceStderr._save_fd)
                except Exception:
                    pass
                SilenceStderr._save_fd = None
                SilenceStderr._null_fd = None

def safe_squeeze(ds):
    drop_dims = [d for d in ['ref_time', 'z', 'generalVerticalLayer', 'heightAboveGround'] if d in ds.dims and ds.sizes[d] == 1]
    if 'eps' in ds.dims and ds.sizes['eps'] == 1:
        drop_dims.append('eps')
    return ds.squeeze(drop_dims) if drop_dims else ds

def get_hhl(valid_cells=None):
    print("-> Lade statische vertikale Gittergeometrie (HHL)...", flush=True)
    url_ch1_vert = ogd_api.get_collection_asset_url(
        collection_id="ch.meteoschweiz.ogd-forecasting-icon-ch1",
        asset_id="vertical_constants_icon-ch1-eps.grib2"
    )
    
    for attempt in range(1, 4):
        try:
            with SilenceStderr():
                ds_vert = grib_decoder.load(
                    source=data_source.URLDataSource(urls=[url_ch1_vert]),
                    request={"param": "HHL"},
                    geo_coords=lambda uuid: {}
                )
            break
        except Exception as e:
            if attempt == 3:
                raise e
            print(f"⚠️ Netzwerkunterbrechung bei HHL (Versuch {attempt}/3). Wiederhole in 3s...", flush=True)
            time.sleep(3)

    hhl_da = ds_vert["HHL"].squeeze()
    if valid_cells is not None:
        hhl_da = hhl_da.isel(cell=valid_cells)
    
    vals = hhl_da.values
    if vals.shape[0] != 81 and vals.shape[-1] == 81:
        vals = np.moveaxis(vals, -1, 0)
    
    print(f"✓ HHL geladen mit Form: {vals.shape} (81 Schichtgrenzen)", flush=True)
    return vals

def interpolate_single_hour_to_1500m(da_hour, hhl_values, target_alt=config.TARGET_ALTITUDE):
    """Vollständig vektorisierte vertikale Interpolation (über alle Member & Zellen gleichzeitig)."""
    num_cells = hhl_values.shape[1]
    col_idx = np.arange(num_cells)

    h_full = 0.5 * (hhl_values[:-1, :] + hhl_values[1:, :])
    hsurf = hhl_values[-1, :]

    is_below = (h_full < target_alt)
    idx_below = np.argmax(is_below, axis=0)
    idx_above = np.maximum(0, idx_below - 1)

    h_a = h_full[idx_above, col_idx]
    h_b = h_full[idx_below, col_idx]
    dh = np.where((h_a - h_b) == 0, 1e-6, h_a - h_b)
    weight = np.clip((target_alt - h_b) / dh, 0.0, 1.0).astype(np.float32)

    mask_underground = (hsurf >= target_alt) | (~np.any(is_below, axis=0))
    z_dim = [d for d in da_hour.dims if d in ['generalVerticalLayer', 'z', 'level']][0]

    # Vektorisierte Berechnung für Ensembles (ohne Python-Schleife!)
    if 'eps' in da_hour.dims and da_hour.sizes['eps'] > 1:
        # Array so ausrichten, dass: Achse 0 = eps, Achse 1 = Vertikalschicht, Achse 2 = cell
        sub = da_hour.squeeze()
        z_axis = sub.dims.index(z_dim)
        eps_axis = sub.dims.index('eps')
        cell_axis = sub.dims.index('cell')
        
        vals_3d = np.transpose(sub.values, (eps_axis, z_axis, cell_axis))  # Shape: (num_eps, 80, num_cells)
        
        # NumPy Advanced Indexing greift alle Member in 1 Operation ab
        v_a = vals_3d[:, idx_above, col_idx]
        v_b = vals_3d[:, idx_below, col_idx]
        
        out_interp = (1.0 - weight) * v_b + weight * v_a
        out_interp[:, mask_underground] = np.nan

        coords = {c: da_hour.coords[c] for c in ['eps', 'cell'] if c in da_hour.coords}
        return xr.DataArray(out_interp, dims=['eps', 'cell'], coords=coords)

    else:
        # Deterministisch (1 Member)
        sub = da_hour.squeeze()
        if sub.dims[0] != z_dim:
            vals_2d = np.moveaxis(sub.values, sub.dims.index(z_dim), 0)
        else:
            vals_2d = sub.values

        v_a = vals_2d[idx_above, col_idx]
        v_b = vals_2d[idx_below, col_idx]
        v_int = (1.0 - weight) * v_b + weight * v_a
        v_int[mask_underground] = np.nan

        coords = {'cell': da_hour.coords['cell']}
        return xr.DataArray(v_int, dims=['cell'], coords=coords)

def fetch_single_2d(var_name, perturbed, ref_time_str, lead_times, valid_cells):
    req = ogd_api.Request(
        collection="ogd-forecasting-icon-ch1",
        variable=var_name,
        ref_time=ref_time_str,
        perturbed=perturbed,
        lead_time=lead_times
    )
    for attempt in range(1, 4):
        try:
            with SilenceStderr():
                ds = ogd_api.get_from_ogd(req)
            if valid_cells is not None:
                ds = ds.isel(cell=valid_cells)
            return safe_squeeze(ds)
        except Exception as e:
            if attempt == 3:
                raise e
            print(f"⚠️ Netzwerkfehler bei {var_name} (Versuch {attempt}/3). Wiederhole in 3s...", flush=True)
            time.sleep(3)

def _fetch_and_slice_single_hour(args):
    var_name, perturbed, ref_time_str, lt, valid_cells, hhl_values = args
    req = ogd_api.Request(
        collection="ogd-forecasting-icon-ch1",
        variable=var_name,
        ref_time=ref_time_str,
        perturbed=perturbed,
        lead_time=[lt]
    )
    
    ds_hour = None
    for attempt in range(1, 4):
        try:
            with SilenceStderr():
                ds_hour = ogd_api.get_from_ogd(req)
            break
        except Exception as e:
            if attempt == 3:
                raise e
            time.sleep(3 * attempt)

    if valid_cells is not None:
        ds_hour = ds_hour.isel(cell=valid_cells)

    ds_1500 = interpolate_single_hour_to_1500m(ds_hour, hhl_values, config.TARGET_ALTITUDE)
    del ds_hour
    gc.collect()
    return ds_1500

def fetch_3d_and_slice(var_name, perturbed, ref_time_str, lead_times, valid_cells, hhl_values):
    label = f"{var_name} 1500m ({'Ensemble' if perturbed else 'Hauptlauf'})"
    total = len(lead_times)
    print(f"-> Verarbeite {label} parallel (3 Worker) für {total} Zeitschritte...", flush=True)

    tasks = [
        (var_name, perturbed, ref_time_str, lt, valid_cells, hhl_values)
        for lt in lead_times
    ]

    # 3 Worker lasten die Netzwerk-Bandbreite optimal aus
    with ThreadPoolExecutor(max_workers=3) as pool:
        hourly_slices = list(pool.map(_fetch_and_slice_single_hour, tasks))

    if len(hourly_slices) > 1:
        return xr.concat(hourly_slices, dim="lead_time")
    else:
        return hourly_slices[0].expand_dims("lead_time")

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
            with SilenceStderr():
                ds_u_h_raw = ogd_api.get_from_ogd(req_pilot)
            break
        except Exception as e:
            if attempt == 3:
                raise e
            print(f"⚠️ Netzwerkfehler beim Pilot-Download (Versuch {attempt}/3). Wiederhole in 3s...", flush=True)
            time.sleep(3)

    lats = ds_u_h_raw.coords['lat'].values
    lons = ds_u_h_raw.coords['lon'].values
    valid_cells = np.where(
        (lats >= config.LAT_MIN) & (lats <= config.LAT_MAX) & 
        (lons >= config.LON_MIN) & (lons <= config.LON_MAX)
    )[0]

    u_h = safe_squeeze(ds_u_h_raw.isel(cell=valid_cells))
    del ds_u_h_raw
    gc.collect()

    print("2. Lade 10m-Felder parallel (3 Streams)...", flush=True)
    tasks_10m = [
        ("V_10M", False),
        ("VMAX_10M", False),
        ("U_10M", True),
        ("V_10M", True),
        ("VMAX_10M", True)
    ]

    with ThreadPoolExecutor(max_workers=3) as pool:
        results_10m = list(pool.map(
            lambda t: fetch_single_2d(t[0], t[1], ref_time_str, lead_times, valid_cells),
            tasks_10m
        ))

    v_h, g_h, u_e, v_e, g_e = results_10m

    print("3. Lade vertikales Höhenprofil & berechne 1500m Wind...", flush=True)
    hhl_values = get_hhl(valid_cells)

    u15_h = fetch_3d_and_slice("U", False, ref_time_str, lead_times, valid_cells, hhl_values)
    v15_h = fetch_3d_and_slice("V", False, ref_time_str, lead_times, valid_cells, hhl_values)
    u15_e = fetch_3d_and_slice("U", True, ref_time_str, lead_times, valid_cells, hhl_values)
    v15_e = fetch_3d_and_slice("V", True, ref_time_str, lead_times, valid_cells, hhl_values)

    del hhl_values
    gc.collect()

    print("✓ Alle Datensätze speicherschonend und parallel bereitgestellt!", flush=True)
    return u_h, v_h, g_h, u_e, v_e, g_e, u15_h, v15_h, u15_e, v15_e

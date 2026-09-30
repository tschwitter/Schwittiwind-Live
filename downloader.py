import gc
import time
from datetime import timedelta
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from meteodatalab import ogd_api
import config

def safe_squeeze(ds):
    """Entfernt nur 1er-Dimensionen von ref_time, z und eps – NIEMALS lead_time!"""
    drop_dims = [d for d in ['ref_time', 'z'] if d in ds.dims and ds.sizes[d] == 1]
    if 'eps' in ds.dims and ds.sizes['eps'] == 1:
        drop_dims.append('eps')
    return ds.squeeze(drop_dims) if drop_dims else ds

def _download_and_crop_task(args):
    var_name, perturbed, ref_time_str, lead_times, valid_cells = args
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
            print(f"✓ [Worker] Fertig & zugeschnitten: {label}", flush=True)
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

    print(f"2. Starte parallelen Download für die restlichen 5 Datensätze...", flush=True)
    tasks = [
        ("V_10M", False, ref_time_str, lead_times, valid_cells),
        ("VMAX_10M", False, ref_time_str, lead_times, valid_cells),
        ("U_10M", True, ref_time_str, lead_times, valid_cells),
        ("V_10M", True, ref_time_str, lead_times, valid_cells),
        ("VMAX_10M", True, ref_time_str, lead_times, valid_cells)
    ]

    with ProcessPoolExecutor(max_workers=2) as executor:
        v_h, g_h, u_e, v_e, g_e = list(executor.map(_download_and_crop_task, tasks))

    print("✓ Alle 6 Wetter-Datensätze für diesen Chunk empfangen!", flush=True)
    gc.collect()

    return u_h, v_h, g_h, u_e, v_e, g_e

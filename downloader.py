import gc
from datetime import timedelta
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from meteodatalab import ogd_api
import config

def _download_and_crop_task(args):
    var_name, perturbed, ref_time_str, lead_times, valid_cells = args
    label = f"{var_name} ({'Ensemble' if perturbed else 'Hauptlauf'})"
    print(f"-> [Worker] Starte Download für {label} ({len(lead_times)} Schritte)...", flush=True)

    req = ogd_api.Request(
        collection="ogd-forecasting-icon-ch1",
        variable=var_name,
        ref_time=ref_time_str,
        perturbed=perturbed,
        lead_time=lead_times
    )
    
    ds = ogd_api.get_from_ogd(req)
    if valid_cells is not None:
        ds = ds.isel(cell=valid_cells)
    ds = ds.squeeze()
        
    print(f"✓ [Worker] Fertig & zugeschnitten: {label}", flush=True)
    return ds

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
    ds_u_h_raw = ogd_api.get_from_ogd(req_pilot)

    # Gittermaske der Schweiz berechnen
    lats = ds_u_h_raw.coords['lat'].values
    lons = ds_u_h_raw.coords['lon'].values
    valid_cells = np.where(
        (lats >= config.LAT_MIN) & (lats <= config.LAT_MAX) & 
        (lons >= config.LON_MIN) & (lons <= config.LON_MAX)
    )[0]

    u_h = ds_u_h_raw.isel(cell=valid_cells).squeeze()
    del ds_u_h_raw
    gc.collect()

    # Paralleler Download der restlichen 5 Datensätze für diesen Chunk
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

import gc
from datetime import timedelta
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from meteodatalab import ogd_api
import config

def _download_and_crop_task(args):
    """
    Eigenständige Worker-Funktion für parallele Prozesse.
    Lädt ein Feld herunter und schneidet es sofort im Worker auf die Schweiz zu.
    """
    var_name, perturbed, ref_time_str, lead_times, valid_cells = args
    label = f"{var_name} ({'Ensemble' if perturbed else 'Hauptlauf'})"
    print(f"-> [Download-Worker] Starte Download für {label}...", flush=True)

    req = ogd_api.Request(
        collection="ogd-forecasting-icon-ch1",
        variable=var_name,
        ref_time=ref_time_str,
        perturbed=perturbed,
        lead_time=lead_times
    )
    
    # 1. Daten von MeteoSchweiz laden
    ds = ogd_api.get_from_ogd(req)
    
    # 2. Sofortiger RAM-Schutz: Erst auf die Schweiz zuschneiden, dann squeeze
    if valid_cells is not None:
        ds = ds.isel(cell=valid_cells)
    ds = ds.squeeze()
        
    print(f"✓ [Download-Worker] Fertig & zugeschnitten: {label}", flush=True)
    return ds

def fetch_weather_data():
    lead_times = [timedelta(hours=h) for h in range(config.ANZAHL_STUNDEN + 1)]

    # STUFE 1: Pilot-Download zur Ermittlung von Referenzzeit und Schweizer Gittergrenzen
    print("1. Pilot-Download: Hole Hauptlauf U_10M zur Koordinaten- & Zeitprüfung...", flush=True)
    req_pilot = ogd_api.Request(
        collection="ogd-forecasting-icon-ch1",
        variable="U_10M",
        ref_time="latest",
        perturbed=False,
        lead_time=lead_times
    )
    ds_u_h_raw = ogd_api.get_from_ogd(req_pilot)
    
    # FEHLER-FIX: Sicherer Zugriff auf ref_time (funktioniert als Array und als Skalar)
    ref_val = ds_u_h_raw.coords['ref_time'].values
    if getattr(ref_val, 'ndim', 0) > 0:
        ref_time_raw = ref_val[0]
    else:
        ref_time_raw = ref_val.item() if hasattr(ref_val, 'item') else ref_val

    ref_time_str = str(ref_time_raw).split('.')[0] + "Z"
    print(f"-> Modellstart festgesetzt auf: {ref_time_str}", flush=True)

    # Schweizer Gittermaske einmalig berechnen
    lats = ds_u_h_raw.coords['lat'].values
    lons = ds_u_h_raw.coords['lon'].values
    valid_cells = np.where(
        (lats >= config.LAT_MIN) & (lats <= config.LAT_MAX) & 
        (lons >= config.LON_MIN) & (lons <= config.LON_MAX)
    )[0]
    print(f"-> Schweizer Gittermaske aktiv ({len(valid_cells)} Zellen).", flush=True)

    # Pilot-Datensatz zuschneiden
    u_h = ds_u_h_raw.isel(cell=valid_cells).squeeze()
    del ds_u_h_raw
    gc.collect()

    # STUFE 2: Die restlichen 5 Datensätze parallel auf 2 Kernen laden
    print("2. Starte parallele 2-Kern-Download-Pipeline für die restlichen 5 Datensätze...", flush=True)
    
    tasks = [
        ("V_10M", False, ref_time_str, lead_times, valid_cells),     # v_h
        ("VMAX_10M", False, ref_time_str, lead_times, valid_cells),  # g_h
        ("U_10M", True, ref_time_str, lead_times, valid_cells),      # u_e
        ("V_10M", True, ref_time_str, lead_times, valid_cells),      # v_e
        ("VMAX_10M", True, ref_time_str, lead_times, valid_cells)   # g_e
    ]

    with ProcessPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(_download_and_crop_task, tasks))

    v_h, g_h, u_e, v_e, g_e = results
    
    print("✓ Alle 6 Wetter-Datensätze erfolgreich und parallel empfangen!", flush=True)
    gc.collect()

    return u_h, v_h, g_h, u_e, v_e, g_e, ref_time_raw

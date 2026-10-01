import os
import gc
import sys
import json
import shutil
import argparse
import urllib.request
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from multiprocessing import get_context
from meteodatalab import ogd_api
import config

SHARED_DATA = {}

def check_if_new_data_available():
    print("--- SCHNELLPRÜFUNG: Suche nach neuem Modelllauf ---", flush=True)
    live_config_url = "https://tschwitter.github.io/Schwittiwind-Live/data/config.json"
    live_ref_time = None
    try:
        req = urllib.request.Request(live_config_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            live_data = json.loads(response.read().decode())
            live_ref_time = live_data.get("ref_time_utc")
            print(f"-> Aktuell auf der Website live: {live_ref_time}", flush=True)
    except Exception as e:
        print(f"-> Hinweis: Konnte Live-Website nicht abfragen ({e}). Fahre fort.", flush=True)
        return True, None, None

    try:
        check_req = ogd_api.Request(
            collection="ogd-forecasting-icon-ch1",
            variable="U_10M",
            ref_time="latest",
            perturbed=False,
            horizon=f"P0DT{config.ANZAHL_STUNDEN}H"
        )
        ds_check = ogd_api.get_from_ogd(check_req)
        latest_ref_raw = ds_check.coords['ref_time'].values
        if getattr(latest_ref_raw, 'ndim', 0) > 0:
            latest_ref_raw = latest_ref_raw[0]
        else:
            latest_ref_raw = latest_ref_raw.item() if hasattr(latest_ref_raw, 'item') else latest_ref_raw

        latest_dt = datetime.fromisoformat(str(latest_ref_raw).split('.')[0])
        latest_ref_str = latest_dt.strftime("%d.%m.%Y %H:00 UTC")
        iso_str = str(latest_ref_raw).split('.')[0] + "Z"

        print(f"-> Vollständig veröffentlichter Lauf: {latest_ref_str}", flush=True)
        
        if live_ref_time and (latest_ref_str == live_ref_time):
            print("=======================================================", flush=True)
            print(" Kein neuer Modelllauf vorhanden. Website ist aktuell!", flush=True)
            print("=======================================================", flush=True)
            return False, latest_ref_str, iso_str
        else:
            print("-> NEUER VOLLSTÄNDIGER LAUF BEREIT! Starte Matrix...", flush=True)
            return True, latest_ref_str, iso_str
    except Exception as e:
        print(f"-> Hinweis: Neuester Lauf noch nicht vollständig bei MeteoSchweiz ({e}).", flush=True)
        print("-> Warte auf den nächsten Check, bis alle Stunden bereit sind.", flush=True)
        return False, None, "latest"

def get_dynamic_chunks(total_steps, max_chunks=4):
    k = min(max_chunks, total_steps)
    base = total_steps // k
    rem = total_steps % k
    chunks = []
    cur = 0
    for i in range(k):
        size = base + (1 if i < rem else 0)
        chunks.append({
            "chunk": i,
            "start": cur,
            "end": cur + size - 1
        })
        cur += size
    return chunks

def prepare_base_site(ref_time_str, iso_str):
    os.makedirs("dist/data", exist_ok=True)
    local_tz = ZoneInfo("Europe/Zurich")
    
    if iso_str and iso_str != "latest":
        ref_dt = datetime.fromisoformat(iso_str.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    else:
        ref_dt = datetime.now(ZoneInfo("UTC"))

    times_by_step = []
    for h in range(config.ANZAHL_STUNDEN + 1):
        valid_local = (ref_dt + timedelta(hours=h)).astimezone(local_tz)
        times_by_step.append({
            "step_hours": h,
            "local_str": valid_local.strftime("%d.%m.%Y %H:%M Local")
        })

    with open("dist/data/times.json", "w") as f:
        json.dump(times_by_step, f)

    member_names = (
        ["Hauptlauf (Control)"] + 
        [f"Ens Member {m}" for m in range(1, 11)] + 
        ["Median", "Min", "Max", "25% Quantil", "75% Quantil", "Interquantilabstand"]
    )

    config_data = {
        "xmin": config.XMIN, "xmax": config.XMAX,
        "ymin": config.YMIN, "ymax": config.YMAX,
        "nx": config.NX, "ny": config.NY,
        "ref_time_utc": ref_time_str or ref_dt.strftime("%d.%m.%Y %H:00 UTC"),
        "member_names": member_names,
        "variables": config.VARIABLES
    }
    with open("dist/data/config.json", "w") as f:
        json.dump(config_data, f)

    shutil.copy("index.html", "dist/index.html")
    print("✓ Basis-Dateien bereitgestellt!", flush=True)

def process_single_local_step(args):
    import stats
    import exporter

    local_idx, global_step_idx = args
    u_h = SHARED_DATA["u_h"]
    v_h = SHARED_DATA["v_h"]
    g_h = SHARED_DATA["g_h"]
    u_e = SHARED_DATA["u_e"]
    v_e = SHARED_DATA["v_e"]
    g_e = SHARED_DATA["g_e"]
    u15_h = SHARED_DATA["u15_h"]
    v15_h = SHARED_DATA["v15_h"]
    u15_e = SHARED_DATA["u15_e"]
    v15_e = SHARED_DATA["v15_e"]
    weights = SHARED_DATA["weights"]

    step_results = stats.compute_timestep(
        u_h, v_h, g_h, u_e, v_e, g_e,
        u15_h, v15_h, u15_e, v15_e,
        local_idx, weights
    )

    for var_name in config.VARIABLES:
        for m_idx, d in step_results[var_name].items():
            exporter.export_variable_step(var_name, m_idx, global_step_idx, d)

    print(f"✓ [Worker {os.getpid()}] Fertig Zeitschritt +{global_step_idx}h (Datei s{global_step_idx})", flush=True)
    return global_step_idx

def run_chunk(start_step, end_step, ref_time_str):
    import downloader
    import stats

    os.makedirs("dist/data", exist_ok=True)
    num_chunk_steps = end_step - start_step + 1

    print(f"--- STARTE CHUNK: Schritte {start_step} bis {end_step} ({num_chunk_steps} Schritte) ---", flush=True)

    u_h, v_h, g_h, u_e, v_e, g_e, u15_h, v15_h, u15_e, v15_e = downloader.fetch_weather_data(start_step, end_step, ref_time_str)

    source_lons = u_h.coords['lon'].values
    source_lats = u_h.coords['lat'].values
    weights = stats.init_regrid_weights(source_lons, source_lats)

    global SHARED_DATA
    SHARED_DATA = {
        "u_h": u_h, "v_h": v_h, "g_h": g_h,
        "u_e": u_e, "v_e": v_e, "g_e": g_e,
        "u15_h": u15_h, "v15_h": v15_h,
        "u15_e": u15_e, "v15_e": v15_e,
        "weights": weights
    }

    tasks = [(local_idx, start_step + local_idx) for local_idx in range(num_chunk_steps)]

    ctx = get_context("fork")
    with ctx.Pool(processes=2) as pool:
        pool.map(process_single_local_step, tasks)

    print(f"=== CHUNK {start_step} bis {end_step} ERFOLGREICH BEENDET ===", flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true", help="Führt Schnellprüfung aus und baut Basisdateien")
    parser.add_argument("--force", action="store_true", help="Erzwingt Neuberechnung")
    parser.add_argument("--start-step", type=int, default=0)
    parser.add_argument("--end-step", type=int, default=33)
    parser.add_argument("--ref-time", type=str, default="latest")
    args = parser.parse_args()

    if args.prepare:
        is_new, latest_ref_str, iso_str = check_if_new_data_available()
        should_run = is_new or args.force
        
        if should_run:
            prepare_base_site(latest_ref_str, iso_str)

        total_steps = config.ANZAHL_STUNDEN + 1
        chunks = get_dynamic_chunks(total_steps, max_chunks=4)
        matrix_payload = {"include": chunks}
        print(f"-> Dynamische Matrix berechnet: {len(chunks)} Server-Jobs:", flush=True)
        for c in chunks:
            print(f"   Server {c['chunk']}: Schritte {c['start']} bis {c['end']}", flush=True)

        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"should_run={'true' if should_run else 'false'}\n")
                f.write(f"ref_time_str={iso_str}\n")
                f.write(f"matrix_config={json.dumps(matrix_payload)}\n")
        sys.exit(0)

    run_chunk(args.start_step, args.end_step, args.ref_time)

if __name__ == "__main__":
    main()

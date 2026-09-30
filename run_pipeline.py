import os
import gc
import sys
import json
import shutil
import urllib.request
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from multiprocessing import get_context
from meteodatalab import ogd_api
import config
import downloader
import stats
import exporter

# Globale Variablen für Copy-on-Write im Multiprocessing
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
        print(f"-> Hinweis: Konnte Live-Website nicht abfragen ({e}). Fahre mit Berechnung fort.", flush=True)
        return True, None

    try:
        check_req = ogd_api.Request(
            collection="ogd-forecasting-icon-ch1",
            variable="U_10M",
            ref_time="latest",
            perturbed=False,
            horizon="P0DT0H"
        )
        ds_check = ogd_api.get_from_ogd(check_req)
        latest_ref_raw = ds_check.coords['ref_time'].values[0]
        latest_dt = datetime.fromisoformat(str(latest_ref_raw).split('.')[0])
        latest_ref_str = latest_dt.strftime("%d.%m.%Y %H:00 UTC")
        print(f"-> Neuester Lauf bei MeteoSchweiz : {latest_ref_str}", flush=True)
        
        if live_ref_time and (latest_ref_str == live_ref_time):
            print("=======================================================", flush=True)
            print(" Kein neuer Modelllauf vorhanden. Website ist aktuell!", flush=True)
            print(" Beende Job nach wenigen Sekunden ohne Berechnung.", flush=True)
            print("=======================================================", flush=True)
            return False, latest_ref_raw
        else:
            print("-> NEUER LAUF GEFUNDEN! Starte vollständige Berechnung...", flush=True)
            return True, latest_ref_raw
    except Exception as e:
        print(f"-> Fehler bei der Schnellabfrage ({e}). Starte reguläre Pipeline sicherheitshalber.", flush=True)
        return True, None

def process_single_step(s_idx):
    """Verarbeitet einen einzelnen Zeitschritt parallel auf einem CPU-Kern."""
    u_h = SHARED_DATA["u_h"]
    v_h = SHARED_DATA["v_h"]
    g_h = SHARED_DATA["g_h"]
    u_e = SHARED_DATA["u_e"]
    v_e = SHARED_DATA["v_e"]
    g_e = SHARED_DATA["g_e"]
    destination = SHARED_DATA["destination"]
    ref_time_dt = SHARED_DATA["ref_time_dt"]
    local_tz = SHARED_DATA["local_tz"]

    print(f"-> [Worker PID {os.getpid()}] Start Zeitschritt {s_idx + 1}...", flush=True)
    
    # 1. Regridding & Statistik-Berechnung für diesen Schritt
    step_results = stats.compute_timestep(u_h, v_h, g_h, u_e, v_e, g_e, s_idx, destination)

    # 2. Exportiere Wind und Böen (Konturen + Pfeile)
    for var_name in config.VARIABLES:
        for m_idx, d in step_results[var_name].items():
            exporter.export_variable_step(var_name, m_idx, s_idx, d)

    # 3. Zeitstempel erfassen
    lead_raw = u_h.coords['lead_time'].values[s_idx]
    delta = timedelta(microseconds=int(lead_raw / 1000))
    valid_local = (ref_time_dt + delta).astimezone(local_tz)

    print(f"✓ [Worker PID {os.getpid()}] Fertig Zeitschritt {s_idx + 1} (+{int(lead_raw / 1e9 / 3600)}h)", flush=True)

    return {
        "step_idx": s_idx,
        "step_hours": int(lead_raw / 1e9 / 3600),
        "local_str": valid_local.strftime("%d.%m.%Y %H:%M Local")
    }

def main():
    force_run = "--force" in sys.argv
    if not force_run:
        is_new, _ = check_if_new_data_available()
        if not is_new:
            if "GITHUB_OUTPUT" in os.environ:
                with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                    f.write("updated=false\n")
            sys.exit(0)

    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("updated=true\n")

    os.makedirs("dist/data", exist_ok=True)

    # 1. Download
    u_h, v_h, g_h, u_e, v_e, g_e, ref_time_raw = downloader.fetch_weather_data()
    destination = stats.get_grid_destination()

    # Zeitstempel & Metadaten
    local_tz = ZoneInfo("Europe/Zurich")
    ref_time_dt = datetime.fromisoformat(str(ref_time_raw).split('.')[0]).replace(tzinfo=ZoneInfo("UTC"))
    
    ensemble_members = u_e.coords['eps'].values
    member_names = (
        ["Hauptlauf (Control)"] + 
        [f"Ens Member {m}" for m in ensemble_members] + 
        ["Median", "Min", "Max", "25% Quantil", "75% Quantil", "Interquantilabstand"]
    )

    num_steps = len(u_h.coords['lead_time'])

    # Daten für die parallelen Prozesse bereitstellen (Linux Copy-on-Write)
    global SHARED_DATA
    SHARED_DATA = {
        "u_h": u_h, "v_h": v_h, "g_h": g_h,
        "u_e": u_e, "v_e": v_e, "g_e": g_e,
        "destination": destination,
        "ref_time_dt": ref_time_dt,
        "local_tz": local_tz
    }

    print(f"Starte parallele 2-Kern-Berechnung für {num_steps} Zeitschritte, 2 Variablen und {len(member_names)} Läufe...", flush=True)

    # 2. PARALLELE BERECHNUNG MIT 2 WORKERN (Volle Auslastung beider vCPUs)
    ctx = get_context("fork")
    with ctx.Pool(processes=2) as pool:
        results = pool.map(process_single_step, range(num_steps))

    # Ergebnisse nach Zeitschritt sortieren
    results.sort(key=lambda x: x["step_idx"])
    times_by_step = [{"step_hours": r["step_hours"], "local_str": r["local_str"]} for r in results]

    # 3. Metadaten schreiben
    with open("dist/data/times.json", "w") as f:
        json.dump(times_by_step, f)

    config_data = {
        "xmin": config.XMIN, "xmax": config.XMAX,
        "ymin": config.YMIN, "ymax": config.YMAX,
        "nx": config.NX, "ny": config.NY,
        "ref_time_utc": ref_time_dt.strftime("%d.%m.%Y %H:00 UTC"),
        "member_names": member_names,
        "variables": config.VARIABLES
    }
    with open("dist/data/config.json", "w") as f:
        json.dump(config_data, f)

    # 4. index.html kopieren
    shutil.copy("index.html", "dist/index.html")
    print("=== Pipeline erfolgreich beendet! Alle Daten liegen in dist/ ===", flush=True)

if __name__ == "__main__":
    main()

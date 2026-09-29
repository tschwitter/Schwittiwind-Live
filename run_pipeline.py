import os
import gc
import sys
import json
import shutil
import urllib.request
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from meteodatalab import ogd_api
import config
import downloader
import stats
import exporter

def check_if_new_data_available():
    """Prüft in wenigen Sekunden, ob MeteoSchweiz einen neueren Lauf hat als die Live-Website."""
    print("--- SCHNELLPRÜFUNG: Suche nach neuem Modelllauf ---")
    
    # 1. Was ist aktuell auf deiner Live-Website online?
    live_config_url = "https://tschwitter.github.io/Schwittiwind-Live/data/config.json"
    live_ref_time = None
    try:
        req = urllib.request.Request(live_config_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            live_data = json.loads(response.read().decode())
            live_ref_time = live_data.get("ref_time_utc")
            print(f"-> Aktuell auf der Website live: {live_ref_time}")
    except Exception as e:
        print(f"-> Hinweis: Konnte Live-Website nicht abfragen ({e}). Fahre mit Berechnung fort.")
        return True, None

    # 2. Was ist der neueste verfügbare Lauf bei MeteoSchweiz? (Winzige 1-Schritt-Abfrage, dauert ~2 Sek.)
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
        print(f"-> Neuester Lauf bei MeteoSchweiz : {latest_ref_str}")
        
        # 3. Vergleichen!
        if live_ref_time and (latest_ref_str == live_ref_time):
            print("=======================================================")
            print(" Kein neuer Modelllauf vorhanden. Website ist aktuell!")
            print(" Beende Job nach wenigen Sekunden ohne Berechnung.")
            print("=======================================================")
            return False, latest_ref_raw
        else:
            print("-> NEUER LAUF GEFUNDEN! Starte vollständige Berechnung...")
            return True, latest_ref_raw
    except Exception as e:
        print(f"-> Fehler bei der Schnellabfrage ({e}). Starte reguläre Pipeline sicherheitshalber.")
        return True, None

def main():
    # Ermöglicht manuelles Erzwingen via Flag (--force)
    force_run = "--force" in sys.argv
    
    if not force_run:
        is_new, _ = check_if_new_data_available()
        if not is_new:
            # Signal an GitHub Actions: Nichts Neues, kein Deploy nötig!
            if "GITHUB_OUTPUT" in os.environ:
                with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                    f.write("updated=false\n")
            sys.exit(0)

    # Signal an GitHub Actions: Neue Daten werden berechnet!
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("updated=true\n")

    os.makedirs("dist/data", exist_ok=True)

    # 1. Download
    u_h, v_h, u_e, v_e, ref_time_raw = downloader.fetch_weather_data()
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
    times_by_step = []

    print(f"Starte Berechnung für {num_steps} Zeitschritte und {len(member_names)} Läufe...")

    # 2. Berechnung & Export
    for s_idx in range(num_steps):
        print(f"-> Verarbeite Zeitschritt {s_idx + 1}/{num_steps}...")
        member_data = stats.compute_timestep(u_h, v_h, u_e, v_e, s_idx, destination)

        for m_idx, d in member_data.items():
            exporter.export_member_step(m_idx, s_idx, d)

        # Zeitstempel erfassen
        lead_raw = u_h.coords['lead_time'].values[s_idx]
        delta = timedelta(microseconds=int(lead_raw / 1000))
        valid_local = (ref_time_dt + delta).astimezone(local_tz)
        times_by_step.append({
            "step_hours": int(lead_raw / 1e9 / 3600),
            "local_str": valid_local.strftime("%d.%m.%Y %H:%M Local")
        })
        gc.collect()

    # 3. Metadaten schreiben
    with open("dist/data/times.json", "w") as f:
        json.dump(times_by_step, f)

    config_data = {
        "xmin": config.XMIN, "xmax": config.XMAX,
        "ymin": config.YMIN, "ymax": config.YMAX,
        "nx": config.NX, "ny": config.NY,
        "ref_time_utc": ref_time_dt.strftime("%d.%m.%Y %H:00 UTC"),
        "member_names": member_names
    }
    with open("dist/data/config.json", "w") as f:
        json.dump(config_data, f)

    # 4. index.html kopieren
    shutil.copy("index.html", "dist/index.html")
    print("=== Pipeline erfolgreich beendet! Alle Daten liegen in dist/ ===")

if __name__ == "__main__":
    main()

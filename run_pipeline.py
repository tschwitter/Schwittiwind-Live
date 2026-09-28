import os
import gc
import json
import shutil
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
import config
import downloader
import stats
import exporter

def main():
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

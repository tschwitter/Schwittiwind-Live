import os
import sys
import gc
import json
import shutil
import argparse
import tempfile
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from multiprocessing import get_context

# ================= DISK-QUOTA FIX =================
WORKSPACE_TMP = os.path.abspath("tmp_scratch")
os.makedirs(WORKSPACE_TMP, exist_ok=True)
os.environ["TMPDIR"] = WORKSPACE_TMP
tempfile.tempdir = WORKSPACE_TMP

try:
    import earthkit.data
    earthkit.data.config.set("cache-policy", "temporary")
except Exception:
    pass

import config

SHARED_DATA = {}

def load_existing_runs(model_name):
    model_base_dir = f"dist/data/{model_name}"
    local_runs_file = f"{model_base_dir}/runs.json"
    
    runs = []
    if os.path.exists(local_runs_file):
        try:
            with open(local_runs_file, "r") as f:
                runs = json.load(f)
        except Exception:
            runs = []

    valid_runs = []
    for r in runs:
        r_id = r.get("id")
        r_dir = f"{model_base_dir}/{r_id}"
        if os.path.isdir(r_dir) and os.path.exists(f"{r_dir}/config.json"):
            valid_runs.append(r)

    return valid_runs

def check_kenda_new_data():
    """Prüft die Verfügbarkeit der neuesten stündlichen KENDA-CH1 Analyse."""
    from meteodatalab import ogd_api
    model_cfg = config.MODELS_CONFIG["kenda-ch1"]
    existing_runs = load_existing_runs("kenda-ch1")
    latest_known_id = existing_runs[0]["id"] if (existing_runs and len(existing_runs) > 0) else None

    try:
        check_pilot = ogd_api.Request(
            collection=model_cfg["collection"],
            variable="U_10M",
            ref_time="latest",
            perturbed=False,
            lead_time=[timedelta(hours=0)]
        )
        ds_pilot = ogd_api.get_from_ogd(check_pilot)
        latest_ref_raw = ds_pilot.coords['ref_time'].values
        if getattr(latest_ref_raw, 'ndim', 0) > 0:
            latest_ref_raw = latest_ref_raw[0]
        else:
            latest_ref_raw = latest_ref_raw.item() if hasattr(latest_ref_raw, 'item') else latest_ref_raw

        latest_dt = datetime.fromisoformat(str(latest_ref_raw).split('.')[0]).replace(tzinfo=ZoneInfo("UTC"))
        latest_ref_str = latest_dt.strftime("%d.%m.%Y %H:00 UTC")
        iso_str = str(latest_ref_raw).split('.')[0] + "Z"
        run_id = latest_dt.strftime("%Y%m%d_%H")
    except Exception as e:
        print(f"-> Hinweis: [kenda-ch1] Konnte neuesten Lauf nicht anfragen ({e}).", flush=True)
        return False, None, "latest", None, None

    is_new = (latest_known_id != run_id)
    if not is_new:
        print(f"-> [kenda-ch1] Analyse {run_id} ist bereits aktuell.", flush=True)
        return False, latest_ref_str, iso_str, run_id, latest_dt

    print(f"✓ [kenda-ch1] Neue Analyse {run_id} bereitgestellt!", flush=True)
    return True, latest_ref_str, iso_str, run_id, latest_dt

def check_ecmwf_new_data():
    """Prüft die Verfügbarkeit des neuesten 0.1° ECMWF-Laufs über Open Data."""
    from ecmwf.opendata import Client

    now_utc = datetime.now(ZoneInfo("UTC"))
    existing_runs = load_existing_runs("ecmwf")
    latest_known_id = existing_runs[0]["id"] if (existing_runs and len(existing_runs) > 0) else None

    client = Client(source="google", model="ifs", resol="0p1")

    try:
        latest_dt = client.latest(type="fc", levtype="sfc", step=24)
        if latest_dt is not None:
            latest_dt = latest_dt.replace(tzinfo=ZoneInfo("UTC"))
            run_id = latest_dt.strftime("%Y%m%d_%H")
            iso_str = latest_dt.strftime("%Y-%m-%dT%H:00:00Z")
            ref_str = latest_dt.strftime("%d.%m.%Y %H:00 UTC")

            is_new = (latest_known_id != run_id)
            if not is_new:
                print(f"-> [ecmwf] Lauf {run_id} ist bereits aktuell.", flush=True)
                return False, ref_str, iso_str, run_id, latest_dt

            print(f"✓ [ecmwf] Neuer 0.1° Lauf {run_id} ist bereit!", flush=True)
            return True, ref_str, iso_str, run_id, latest_dt
    except Exception as e:
        print(f"-> Hinweis: [ecmwf] Automatische client.latest() Abfrage fehlgeschlagen ({e}). Prüfe Kandidaten manuell...", flush=True)

    candidate_hours = [0, 6, 12, 18]
    candidates = []
    for days_back in [0, 1]:
        d = now_utc.date() - timedelta(days=days_back)
        for h in candidate_hours:
            dt = datetime(d.year, d.month, d.day, h, 0, 0, tzinfo=ZoneInfo("UTC"))
            if dt <= now_utc:
                candidates.append(dt)

    candidates.sort(reverse=True)

    for run_dt in candidates[:4]:
        date_ymd = int(run_dt.strftime("%Y%m%d"))
        cycle_hh = int(run_dt.strftime("%H"))
        run_id = run_dt.strftime("%Y%m%d_%H")
        iso_str = run_dt.strftime("%Y-%m-%dT%H:00:00Z")
        ref_str = run_dt.strftime("%d.%m.%Y %H:00 UTC")

        test_url = f"https://data.ecmwf.int/forecasts/{date_ymd}/{cycle_hh:02d}z/ifs/0p1/enfo/{date_ymd}{cycle_hh:02d}0000-0h-enfo-ef-sfc.grib2"
        try:
            import requests
            r = requests.head(test_url, timeout=5)
            if r.status_code == 200:
                is_new = (latest_known_id != run_id)
                if not is_new:
                    print(f"-> [ecmwf] Lauf {run_id} ist bereits aktuell.", flush=True)
                    return False, ref_str, iso_str, run_id, run_dt
                print(f"✓ [ecmwf] Neuer Lauf {run_id} gefunden via Index!", flush=True)
                return True, ref_str, iso_str, run_id, run_dt
        except Exception:
            pass

    fallback_dt = candidates[0]
    return False, fallback_dt.strftime("%d.%m.%Y %H:00 UTC"), fallback_dt.strftime("%Y-%m-%dT%H:00:00Z"), fallback_dt.strftime("%Y%m%d_%H"), fallback_dt

def check_arome_new_data():
    import requests

    now_utc = datetime.now(ZoneInfo("UTC"))
    existing_runs = load_existing_runs("arome")
    latest_known_id = existing_runs[0]["id"] if (existing_runs and len(existing_runs) > 0) else None

    candidate_hours = [0, 3, 6, 9, 12, 15, 18, 21]
    candidates = []
    for days_back in [0, 1]:
        d = now_utc.date() - timedelta(days=days_back)
        for h in candidate_hours:
            dt = datetime(d.year, d.month, d.day, h, 0, 0, tzinfo=ZoneInfo("UTC"))
            if dt <= now_utc:
                candidates.append(dt)

    candidates.sort(reverse=True)

    for run_dt in candidates[:4]:
        iso_str = run_dt.strftime("%Y-%m-%dT%H:00:00Z")
        run_id = run_dt.strftime("%Y%m%d_%H")
        ref_str = run_dt.strftime("%d.%m.%Y %H:00 UTC")

        test_url = f"https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net/pnt/{iso_str}/arome/001/SP1/arome__001__SP1__42H__{iso_str}.grib2"
        try:
            r = requests.head(test_url, timeout=5)
            if r.status_code == 200:
                is_new = (latest_known_id != run_id)
                if not is_new:
                    print(f"-> [arome] Lauf {run_id} ist bereits aktuell.", flush=True)
                    return False, ref_str, iso_str, run_id, run_dt
                print(f"✓ [arome] Neuer Lauf {run_id} ist vollständig bereit!", flush=True)
                return True, ref_str, iso_str, run_id, run_dt
        except Exception:
            pass

    return False, None, "latest", None, None

def check_icond2_new_data():
    import requests

    now_utc = datetime.now(ZoneInfo("UTC"))
    existing_runs = load_existing_runs("icon-d2")
    latest_known_id = existing_runs[0]["id"] if (existing_runs and len(existing_runs) > 0) else None

    candidate_hours = [0, 3, 6, 9, 12, 15, 18, 21]
    candidates = []
    for days_back in [0, 1]:
        d = now_utc.date() - timedelta(days=days_back)
        for h in candidate_hours:
            dt = datetime(d.year, d.month, d.day, h, 0, 0, tzinfo=ZoneInfo("UTC"))
            if dt <= now_utc:
                candidates.append(dt)

    candidates.sort(reverse=True)

    for run_dt in candidates[:4]:
        cycle_hh = run_dt.strftime("%H")
        date_ymd = run_dt.strftime("%Y%m%d")
        iso_str = run_dt.strftime("%Y-%m-%dT%H:00:00Z")
        run_id = run_dt.strftime("%Y%m%d_%H")
        ref_str = run_dt.strftime("%d.%m.%Y %H:00 UTC")

        test_url = f"https://opendata.dwd.de/weather/nwp/icon-d2-eps/grib/{cycle_hh}/u_10m/icon-d2-eps_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_048_2d_u_10m.grib2.bz2"
        try:
            r = requests.head(test_url, timeout=5)
            if r.status_code == 200:
                is_new = (latest_known_id != run_id)
                if not is_new:
                    print(f"-> [icon-d2] Lauf {run_id} ist bereits aktuell.", flush=True)
                    return False, ref_str, iso_str, run_id, run_dt
                print(f"✓ [icon-d2] Neuer Ensemble-Lauf {run_id} ist vollständig bis +48h bereit!", flush=True)
                return True, ref_str, iso_str, run_id, run_dt
        except Exception:
            pass

    return False, None, "latest", None, None

def check_model_new_data(model_name):
    if model_name == "kenda-ch1":
        return check_kenda_new_data()
    if model_name == "ecmwf":
        return check_ecmwf_new_data()
    if model_name == "arome":
        return check_arome_new_data()
    if model_name == "icon-d2":
        return check_icond2_new_data()

    from meteodatalab import ogd_api
    model_cfg = config.MODELS_CONFIG[model_name]
    existing_runs = load_existing_runs(model_name)
    latest_known_id = existing_runs[0]["id"] if (existing_runs and len(existing_runs) > 0) else None

    try:
        check_pilot = ogd_api.Request(
            collection=model_cfg["collection"],
            variable="U_10M",
            ref_time="latest",
            perturbed=False,
            lead_time=[timedelta(hours=1)]
        )
        ds_pilot = ogd_api.get_from_ogd(check_pilot)
        latest_ref_raw = ds_pilot.coords['ref_time'].values
        if getattr(latest_ref_raw, 'ndim', 0) > 0:
            latest_ref_raw = latest_ref_raw[0]
        else:
            latest_ref_raw = latest_ref_raw.item() if hasattr(latest_ref_raw, 'item') else latest_ref_raw

        latest_dt = datetime.fromisoformat(str(latest_ref_raw).split('.')[0]).replace(tzinfo=ZoneInfo("UTC"))
        latest_ref_str = latest_dt.strftime("%d.%m.%Y %H:00 UTC")
        iso_str = str(latest_ref_raw).split('.')[0] + "Z"
        run_id = latest_dt.strftime("%Y%m%d_%H")
    except Exception as e:
        print(f"-> Hinweis: [{model_name}] Konnte neuesten Lauf nicht anfragen ({e}).", flush=True)
        return False, None, "latest", None, None

    is_new = (latest_known_id != run_id)
    if not is_new:
        print(f"-> [{model_name}] Lauf {run_id} ist bereits aktuell.", flush=True)
        return False, latest_ref_str, iso_str, run_id, latest_dt

    required_hours = 33 if model_name == "icon-ch1" else (120 if latest_dt.hour in [0, 12] else 45)

    try:
        check_final = ogd_api.Request(
            collection=model_cfg["collection"],
            variable="U_10M",
            ref_time=iso_str,
            perturbed=False,
            lead_time=[timedelta(hours=required_hours)]
        )
        ds_final = ogd_api.get_from_ogd(check_final)
        print(f"✓ [{model_name}] Neuer Lauf {run_id} ist vollständig bis +{required_hours}h bereit!", flush=True)
        return True, latest_ref_str, iso_str, run_id, latest_dt
    except Exception:
        print(f"-> Warten: [{model_name}] Lauf {run_id} wird noch von MeteoSchweiz berechnet (+{required_hours}h fehlt).", flush=True)
        return False, latest_ref_str, iso_str, run_id, latest_dt

def get_dynamic_chunks(total_steps, max_chunks=4):
    k = min(max_chunks, total_steps)
    base = total_steps // k
    rem = total_steps % k
    chunks = []
    cur = 0
    for i in range(k):
        size = base + (1 if i < rem else 0)
        chunks.append({"chunk": i, "start": cur, "end": cur + size - 1})
        cur += size
    return chunks

def prepare_model_base_site(model_name, ref_time_str, iso_str, run_id, run_dt):
    model_cfg = config.MODELS_CONFIG[model_name]
    nx = model_cfg.get("nx", config.NX)
    ny = model_cfg.get("ny", config.NY)
    
    for base_folder in ["dist/data", "dist-meta/data"]:
        model_base_dir = f"{base_folder}/{model_name}"
        run_dir = f"{model_base_dir}/{run_id}"
        os.makedirs(run_dir, exist_ok=True)
        local_tz = ZoneInfo("Europe/Zurich")

        if iso_str and iso_str != "latest" and iso_str != "None":
            ref_dt = datetime.fromisoformat(iso_str.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
        else:
            ref_dt = datetime.now(ZoneInfo("UTC"))

        times_by_step = []
        if model_name == "kenda-ch1":
            # 24 rollende Analyse-Stunden: Schritt 0 ist T-23h, Schritt 23 ist T (aktuell)
            for h in range(24):
                step_dt = ref_dt - timedelta(hours=(23 - h))
                valid_local = step_dt.astimezone(local_tz)
                times_by_step.append({
                    "step_hours": h,
                    "local_str": valid_local.strftime("%d.%m.%Y %H:%M Local")
                })
        else:
            step_hours = config.get_model_step_hours(model_name, ref_dt)
            for h in step_hours:
                valid_local = (ref_dt + timedelta(hours=h)).astimezone(local_tz)
                times_by_step.append({
                    "step_hours": h,
                    "local_str": valid_local.strftime("%d.%m.%Y %H:%M Local")
                })

        with open(f"{run_dir}/times.json", "w") as f:
            json.dump(times_by_step, f)

        num_ens = model_cfg["max_members"] - 1
        if num_ens > 0:
            member_names = (
                ["Hauptlauf"] + 
                [f"Ens Member {m}" for m in range(1, num_ens + 1)] + 
                ["Median", "Min", "Max", "25% Quantil", "75% Quantil", "Interquantilabstand"]
            )
        else:
            member_names = ["Hauptlauf"]

        active_cfg = {}
        for v in model_cfg["active_variables"]:
            if v in config.VARIABLES_CONFIG:
                cfg = dict(config.VARIABLES_CONFIG[v])
                cfg["has_ensemble"] = (v in model_cfg["ensemble_variables"])
                active_cfg[v] = cfg

        config_data = {
            "model_name": model_name,
            "run_id": run_id,
            "model_label": model_cfg["name"],
            "xmin": config.XMIN, "xmax": config.XMAX,
            "ymin": config.YMIN, "ymax": config.YMAX,
            "nx": nx, "ny": ny,
            "ref_time_utc": ref_time_str or ref_dt.strftime("%d.%m.%Y %H:00 UTC"),
            "member_names": member_names,
            "variables": model_cfg["active_variables"],
            "variables_config": active_cfg,
            "palettes": {
                "wind":      {"levels": config.LEVELS,           "colors": config.COLORS},
                "sun":       {"levels": config.SUN_LEVELS,       "colors": config.SUN_COLORS},
                "dbz":       {"levels": config.DBZ_LEVELS,       "colors": config.DBZ_COLORS},
                "cloud":     {"levels": config.CLOUD_LEVELS,     "colors": config.CLOUD_COLORS},
                "iqr_wind":  {"levels": config.IQR_WIND_LEVELS,  "colors": config.IQR_WIND_COLORS},
                "iqr_dbz":   {"levels": config.IQR_DBZ_LEVELS,   "colors": config.IQR_DBZ_COLORS},
                "iqr_sun":   {"levels": config.IQR_SUN_LEVELS,   "colors": config.IQR_SUN_COLORS},
                "iqr_cloud": {"levels": config.IQR_CLOUD_LEVELS, "colors": config.IQR_CLOUD_COLORS}
            }
        }
        with open(f"{run_dir}/config.json", "w") as f:
            json.dump(config_data, f)

        existing_runs = load_existing_runs(model_name)
        existing_runs = [r for r in existing_runs if r.get("id") != run_id]

        run_label = run_dt.strftime("%d.%m. %HZ") if run_dt else run_id
        new_entry = {
            "id": run_id,
            "label": run_label,
            "ref_time_utc": ref_time_str
        }
        updated_runs = [new_entry] + existing_runs
        max_runs = model_cfg.get("max_runs", 4)
        valid_runs = updated_runs[:max_runs]

        with open(f"{model_base_dir}/runs.json", "w") as f:
            json.dump(valid_runs, f)

    print(f"✓ Metadaten für [{model_name} / {run_id}] bereitgestellt ({nx}x{ny}, {len(times_by_step)} Schritte)!", flush=True)

def prune_old_runs():
    print("--- PRUNING: Bereinige Läufe & Historie ---", flush=True)
    base_data_dir = "dist/data"

    for m_name, m_cfg in config.MODELS_CONFIG.items():
        model_base_dir = f"{base_data_dir}/{m_name}"
        if not os.path.exists(model_base_dir):
            continue

        runs_file = f"{model_base_dir}/runs.json"
        valid_runs = []
        if os.path.exists(runs_file):
            try:
                with open(runs_file, "r") as f:
                    valid_runs = json.load(f)
            except Exception:
                valid_runs = []

        valid_ids = [r["id"] for r in valid_runs]
        latest_run_id = valid_ids[0] if valid_ids else None
        num_ens = m_cfg["max_members"] - 1

        for entry in os.listdir(model_base_dir):
            entry_path = os.path.join(model_base_dir, entry)
            if os.path.isfile(entry_path):
                if entry != "runs.json":
                    os.remove(entry_path)
            elif os.path.isdir(entry_path):
                if entry not in valid_ids:
                    print(f"-> Entferne Lauf älter als 24h ({m_name}): {entry}", flush=True)
                    shutil.rmtree(entry_path, ignore_errors=True)
                elif entry != latest_run_id and num_ens > 0:
                    pruned_count = 0
                    for fname in os.listdir(entry_path):
                        if fname.startswith("grid_") and "_m" in fname:
                            try:
                                m_idx = int(fname.split("_m")[1].split("_s")[0])
                                if 1 <= m_idx <= num_ens:
                                    os.remove(os.path.join(entry_path, fname))
                                    pruned_count += 1
                            except Exception:
                                pass
                    if pruned_count > 0:
                        print(f"✓ Historischer Lauf {entry} ({m_name}): {pruned_count} Einzel-Member-Dateien entfernt.", flush=True)

def process_single_local_step(args):
    import stats
    import exporter

    model_name, run_id, local_idx, global_step_idx = args
    weather_data = SHARED_DATA["weather_data"]
    weights = SHARED_DATA["weights"]

    step_results = stats.compute_timestep(model_name, weather_data, local_idx, weights)

    for var_name, d_by_member in step_results.items():
        for m_idx, d in d_by_member.items():
            exporter.export_variable_step(model_name, run_id, var_name, m_idx, global_step_idx, d)

    print(f"✓ [{model_name}/{run_id}] Fertig Zeitschritt Index {global_step_idx}", flush=True)
    return global_step_idx

def run_chunk(model_name, run_id, start_step, end_step, ref_time_str):
    import downloader
    import stats

    if not ref_time_str or ref_time_str == "None":
        ref_time_str = "latest"

    os.makedirs(f"dist/data/{model_name}/{run_id}", exist_ok=True)
    num_chunk_steps = end_step - start_step + 1

    print(f"--- STARTE [{model_name} / {run_id}]: Schritte {start_step} bis {end_step} ({num_chunk_steps} Schritte) ---", flush=True)
    weather_data = downloader.fetch_weather_data(model_name, start_step, end_step, ref_time_str)

    weights = stats.init_regrid_weights(model_name, weather_data["ref_lon"], weather_data["ref_lat"])

    global SHARED_DATA
    SHARED_DATA = {
        "weather_data": weather_data,
        "weights": weights
    }

    tasks = [(model_name, run_id, local_idx, start_step + local_idx) for local_idx in range(num_chunk_steps)]

    num_procs = min(4, os.cpu_count() or 2)
    ctx = get_context("fork")
    with ctx.Pool(processes=num_procs) as pool:
        pool.map(process_single_local_step, tasks)

    try:
        shutil.rmtree(WORKSPACE_TMP, ignore_errors=True)
        os.makedirs(WORKSPACE_TMP, exist_ok=True)
    except Exception:
        pass

    print(f"=== [{model_name} / {run_id}] CHUNK {start_step} bis {end_step} BEENDET ===", flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--prune", action="store_true")
    parser.add_argument("--model", type=str, default="icon-ch1")
    parser.add_argument("--run-id", type=str, default="latest")
    parser.add_argument("--start-step", type=int, default=0)
    parser.add_argument("--end-step", type=int, default=33)
    parser.add_argument("--ref-time", type=str, default="latest")
    args = parser.parse_args()

    if args.prune:
        prune_old_runs()
        sys.exit(0)

    if args.prepare:
        os.makedirs("dist-meta/data", exist_ok=True)
        
        for static_file in ["index.html", "style.css", "app.js"]:
            if os.path.exists(static_file):
                shutil.copy(static_file, f"dist-meta/{static_file}")

        all_chunks = []
        any_new = False

        for m_name, m_cfg in config.MODELS_CONFIG.items():
            is_new, latest_ref_str, iso_str, run_id, run_dt = check_model_new_data(m_name)
            should_run_m = is_new or args.force
            if should_run_m and run_id:
                any_new = True
                prepare_model_base_site(m_name, latest_ref_str, iso_str, run_id, run_dt)
                
                step_hours = config.get_model_step_hours(m_name, run_dt)
                total_steps = len(step_hours)
                
                c_list = get_dynamic_chunks(total_steps, max_chunks=m_cfg.get("max_chunks", 4))
                for c in c_list:
                    all_chunks.append({
                        "model": m_name,
                        "run_id": run_id,
                        "chunk": c["chunk"],
                        "start": c["start"],
                        "end": c["end"],
                        "ref_time": iso_str
                    })

        should_run = any_new or args.force
        matrix_payload = {"include": all_chunks}
        print(f"-> Matrix vorbereitet: {len(all_chunks)} Jobs über alle Modelle.", flush=True)

        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"should_run={'true' if should_run else 'false'}\n")
                f.write(f"matrix_config={json.dumps(matrix_payload)}\n")
        sys.exit(0)

    run_chunk(args.model, args.run_id, args.start_step, args.end_step, args.ref_time)

if __name__ == "__main__":
    main()

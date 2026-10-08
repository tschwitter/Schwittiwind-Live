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
import config

SHARED_DATA = {}

def load_existing_runs(model_name):
    """Lädt nur Läufe, deren Ordner lokal auch tatsächlich existieren."""
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

def check_model_new_data(model_name):
    from meteodatalab import ogd_api

    model_cfg = config.MODELS_CONFIG[model_name]
    existing_runs = load_existing_runs(model_name)
    latest_known_id = existing_runs[0]["id"] if (existing_runs and len(existing_runs) > 0) else None

    try:
        check_req = ogd_api.Request(
            collection=model_cfg["collection"],
            variable="U_10M",
            ref_time="latest",
            perturbed=False,
            lead_time=[timedelta(hours=1)]
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
        run_id = latest_dt.strftime("%Y%m%d_%H")

        is_new = (latest_known_id != run_id)
        print(f"-> [{model_name}] Neueste Daten: {latest_ref_str} (ID: {run_id}) | Neu: {is_new}", flush=True)
        return is_new, latest_ref_str, iso_str, run_id, latest_dt
    except Exception as e:
        print(f"-> Hinweis: [{model_name}] Fehler beim Abruf von MeteoSchweiz ({e}).", flush=True)
        return False, None, "latest", None, None

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
        for h in range(model_cfg["hours"] + 1):
            valid_local = (ref_dt + timedelta(hours=h)).astimezone(local_tz)
            times_by_step.append({
                "step_hours": h,
                "local_str": valid_local.strftime("%d.%m.%Y %H:%M Local")
            })

        with open(f"{run_dir}/times.json", "w") as f:
            json.dump(times_by_step, f)

        num_ens = model_cfg["max_members"] - 1
        member_names = (
            ["Hauptlauf"] + 
            [f"Ens Member {m}" for m in range(1, num_ens + 1)] + 
            ["Median", "Min", "Max", "25% Quantil", "75% Quantil", "Interquantilabstand"]
        )

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
            "nx": config.NX, "ny": config.NY,
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

        # runs.json mit genau 8 Läufen (CH1) bzw. 4 Läufen (CH2)
        existing_runs = load_existing_runs(model_name)
        existing_runs = [r for r in existing_runs if r.get("id") != run_id]

        run_label = run_dt.strftime("%d.%m. %HZ") if run_dt else run_id
        new_entry = {
            "id": run_id,
            "label": run_label,
            "ref_time_utc": ref_time_str
        }
        updated_runs = [new_entry] + existing_runs
        max_runs = model_cfg.get("max_runs", 8)
        valid_runs = updated_runs[:max_runs]

        with open(f"{model_base_dir}/runs.json", "w") as f:
            json.dump(valid_runs, f)

    print(f"✓ Metadaten für [{model_name} / {run_id}] bereitgestellt!", flush=True)

def prune_old_runs():
    """Löscht veraltete Läufe (> 24h) und alle losen Altdateien zuverlässig."""
    print("--- PRUNING: Bereinige Läufe älter als 24h ---", flush=True)
    base_data_dir = "dist/data"
    if os.path.exists(base_data_dir):
        for f in os.listdir(base_data_dir):
            fp = os.path.join(base_data_dir, f)
            if os.path.isfile(fp):
                os.remove(fp)

    for m_name in config.MODELS_CONFIG.keys():
        model_base_dir = f"dist/data/{m_name}"
        if not os.path.exists(model_base_dir):
            continue

        runs_file = f"{model_base_dir}/runs.json"
        valid_ids = set()
        if os.path.exists(runs_file):
            try:
                with open(runs_file, "r") as f:
                    valid_runs = json.load(f)
                valid_ids = set(r["id"] for r in valid_runs)
            except Exception:
                pass

        for entry in os.listdir(model_base_dir):
            entry_path = os.path.join(model_base_dir, entry)
            if os.path.isfile(entry_path):
                if entry != "runs.json":
                    os.remove(entry_path)
            elif os.path.isdir(entry_path):
                if entry not in valid_ids:
                    print(f"-> Entferne Lauf älter als 24h ({m_name}): {entry}", flush=True)
                    shutil.rmtree(entry_path, ignore_errors=True)

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

    print(f"✓ [{model_name}/{run_id}] Fertig Zeitschritt +{global_step_idx}h", flush=True)
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

    weights = stats.init_regrid_weights(weather_data["ref_lon"], weather_data["ref_lat"])

    global SHARED_DATA
    SHARED_DATA = {
        "weather_data": weather_data,
        "weights": weights
    }

    tasks = [(model_name, run_id, local_idx, start_step + local_idx) for local_idx in range(num_chunk_steps)]

    ctx = get_context("fork")
    with ctx.Pool(processes=2) as pool:
        pool.map(process_single_local_step, tasks)

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
        shutil.copy("index.html", "dist-meta/index.html")

        all_chunks = []
        any_new = False

        for m_name, m_cfg in config.MODELS_CONFIG.items():
            is_new, latest_ref_str, iso_str, run_id, run_dt = check_model_new_data(m_name)
            should_run_m = is_new or args.force
            if should_run_m and run_id:
                any_new = True
                prepare_model_base_site(m_name, latest_ref_str, iso_str, run_id, run_dt)
                total_steps = m_cfg["hours"] + 1
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

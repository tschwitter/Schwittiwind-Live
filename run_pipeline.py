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

def check_model_new_data(model_name):
    model_cfg = config.MODELS_CONFIG[model_name]
    live_config_url = f"https://tschwitter.github.io/Schwittiwind-Live/data/{model_name}/config.json"
    live_ref_time = None
    try:
        req = urllib.request.Request(live_config_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            live_data = json.loads(response.read().decode())
            live_ref_time = live_data.get("ref_time_utc")
    except Exception:
        pass

    try:
        check_req = ogd_api.Request(
            collection=model_cfg["collection"],
            variable="U_10M",
            ref_time="latest",
            perturbed=False,
            horizon=f"P0DT{model_cfg['hours']}H"
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

        is_new = (live_ref_time != latest_ref_str)
        return is_new, latest_ref_str, iso_str
    except Exception as e:
        print(f"-> Hinweis: {model_name} noch nicht vollständig ({e}).", flush=True)
        return False, None, "latest"

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

def prepare_model_base_site(model_name, ref_time_str, iso_str):
    model_cfg = config.MODELS_CONFIG[model_name]
    model_dir = f"dist/data/{model_name}"
    os.makedirs(model_dir, exist_ok=True)
    local_tz = ZoneInfo("Europe/Zurich")

    if iso_str and iso_str != "latest":
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

    with open(f"{model_dir}/times.json", "w") as f:
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
    with open(f"{model_dir}/config.json", "w") as f:
        json.dump(config_data, f)

    print(f"✓ Basis-Dateien für [{model_name}] bereitgestellt!", flush=True)

def process_single_local_step(args):
    import stats
    import exporter

    model_name, local_idx, global_step_idx = args
    weather_data = SHARED_DATA["weather_data"]
    weights = SHARED_DATA["weights"]

    step_results = stats.compute_timestep(model_name, weather_data, local_idx, weights)

    for var_name, d_by_member in step_results.items():
        for m_idx, d in d_by_member.items():
            exporter.export_variable_step(model_name, var_name, m_idx, global_step_idx, d)

    print(f"✓ [{model_name}] Fertig Zeitschritt +{global_step_idx}h", flush=True)
    return global_step_idx

def run_chunk(model_name, start_step, end_step, ref_time_str):
    import downloader
    import stats

    os.makedirs(f"dist/data/{model_name}", exist_ok=True)
    num_chunk_steps = end_step - start_step + 1

    print(f"--- STARTE [{model_name}]: Schritte {start_step} bis {end_step} ({num_chunk_steps} Schritte) ---", flush=True)
    weather_data = downloader.fetch_weather_data(model_name, start_step, end_step, ref_time_str)

    weights = stats.init_regrid_weights(weather_data["ref_lon"], weather_data["ref_lat"])

    global SHARED_DATA
    SHARED_DATA = {
        "weather_data": weather_data,
        "weights": weights
    }

    tasks = [(model_name, local_idx, start_step + local_idx) for local_idx in range(num_chunk_steps)]

    ctx = get_context("fork")
    with ctx.Pool(processes=2) as pool:
        pool.map(process_single_local_step, tasks)

    print(f"=== [{model_name}] CHUNK {start_step} bis {end_step} BEENDET ===", flush=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--model", type=str, default="icon-ch1")
    parser.add_argument("--start-step", type=int, default=0)
    parser.add_argument("--end-step", type=int, default=33)
    parser.add_argument("--ref-time", type=str, default="latest")
    args = parser.parse_args()

    if args.prepare:
        os.makedirs("dist/data", exist_ok=True)
        shutil.copy("index.html", "dist/index.html")

        all_chunks = []
        any_new = False

        for m_name, m_cfg in config.MODELS_CONFIG.items():
            is_new, latest_ref_str, iso_str = check_model_new_data(m_name)
            should_run_m = is_new or args.force
            if should_run_m:
                any_new = True
                prepare_model_base_site(m_name, latest_ref_str, iso_str)
                total_steps = m_cfg["hours"] + 1
                c_list = get_dynamic_chunks(total_steps, max_chunks=m_cfg.get("max_chunks", 4))
                for c in c_list:
                    all_chunks.append({
                        "model": m_name,
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

    run_chunk(args.model, args.start_step, args.end_step, args.ref_time)

if __name__ == "__main__":
    main()

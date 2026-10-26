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
import requests

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
    """Lädt bestehende gültige Runs aus runs.json."""
    model_base_dir = f"dist/data/{model_name}"
    runs_file = f"{model_base_dir}/runs.json"
    if not os.path.exists(runs_file):
        return []
    try:
        with open(runs_file, "r") as f:
            runs = json.load(f)
        return [r for r in runs if os.path.exists(f"{model_base_dir}/{r.get('id')}/config.json")]
    except Exception:
        return []

def _generate_candidate_dts(hours_list):
    """Generiert UTC-Kandidatenzeiten für heute und gestern."""
    now_utc = datetime.now(ZoneInfo("UTC"))
    candidates = [
        datetime(d.year, d.month, d.day, h, 0, 0, tzinfo=ZoneInfo("UTC"))
        for days_back in [0, 1]
        for d in [(now_utc.date() - timedelta(days=days_back))]
        for h in hours_list
    ]
    return sorted([dt for dt in candidates if dt <= now_utc], reverse=True)[:4]

def _check_http_candidates(model_name, hours_list, url_template):
    """Allgemeiner Prüfer für HTTP-Header-basierte Datenquellen (ECMWF, AROME, ICON-D2)."""
    existing_runs = load_existing_runs(model_name)
    latest_known_id = existing_runs[0]["id"] if existing_runs else None

    for run_dt in _generate_candidate_dts(hours_list):
        run_id = run_dt.strftime("%Y%m%d_%H")
        iso_str = run_dt.strftime("%Y-%m-%dT%H:00:00Z")
        ref_str = run_dt.strftime("%d.%m.%Y %H:00 UTC")

        url = url_template(run_dt, iso_str)
        try:
            if requests.head(url, timeout=6).status_code == 200:
                is_new = (latest_known_id != run_id)
                if not is_new:
                    print(f"-> [{model_name}] Lauf {run_id} ist bereits aktuell.", flush=True)
                    return False, ref_str, iso_str, run_id, run_dt
                print(f"✓ [{model_name}] Neuer Lauf {run_id} gefunden!", flush=True)
                return True, ref_str, iso_str, run_id, run_dt
        except Exception:
            pass

    return False, None, "latest", None, None

def check_model_new_data(model_name):
    """Prüft zentral, ob ein neuer Lauf für das jeweilige Modell verfügbar ist."""
    if model_name == "arome":
        return _check_http_candidates(
            "arome", [0, 3, 6, 9, 12, 15, 18, 21],
            lambda dt, iso: f"https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net/pnt/{iso}/arome/001/SP1/arome__001__SP1__42H__{iso}.grib2"
        )
    if model_name == "icon-d2":
        return _check_http_candidates(
            "icon-d2", [0, 3, 6, 9, 12, 15, 18, 21],
            lambda dt, iso: f"https://opendata.dwd.de/weather/nwp/icon-d2-eps/grib/{dt.strftime('%H')}/u_10m/icon-d2-eps_germany_icosahedral_single-level_{dt.strftime('%Y%m%d%H')}_048_2d_u_10m.grib2.bz2"
        )
    if model_name == "ecmwf":
        # Primär über Client, Fallback auf HTTP-Index
        try:
            from ecmwf.opendata import Client
            latest_dt = Client(source="google", model="ifs", resol="0p1").latest(type="fc", levtype="sfc", step=24)
            if latest_dt:
                latest_dt = latest_dt.replace(tzinfo=ZoneInfo("UTC"))
                run_id = latest_dt.strftime("%Y%m%d_%H")
                existing = load_existing_runs("ecmwf")
                is_new = not (existing and existing[0]["id"] == run_id)
                return is_new, latest_dt.strftime("%d.%m.%Y %H:00 UTC"), latest_dt.strftime("%Y-%m-%dT%H:00:00Z"), run_id, latest_dt
        except Exception:
            pass
        return _check_http_candidates(
            "ecmwf", [0, 6, 12, 18],
            lambda dt, iso: f"https://data.ecmwf.int/forecasts/{dt.strftime('%Y%m%d')}/{dt.strftime('%H')}z/ifs/0p1/enfo/{dt.strftime('%Y%m%d%H')}0000-0h-enfo-ef-sfc.grib2"
        )

    # MeteoSchweiz OGD (kenda-ch1, icon-ch1, icon-ch2)
    from meteodatalab import ogd_api
    model_cfg = config.MODELS_CONFIG[model_name]
    existing_runs = load_existing_runs(model_name)
    latest_known_id = existing_runs[0]["id"] if existing_runs else None

    try:
        check_pilot = ogd_api.Request(
            collection=model_cfg["collection"], variable="U_10M", ref_time="latest",
            perturbed=False, lead_time=[timedelta(hours=0 if model_name == "kenda-ch1" else 1)]
        )
        ds = ogd_api.get_from_ogd(check_pilot)
        raw_ref = ds.coords['ref_time'].values
        raw_ref = raw_ref[0] if getattr(raw_ref, 'ndim', 0) > 0 else (raw_ref.item() if hasattr(raw_ref, 'item') else raw_ref)
        latest_dt = datetime.fromisoformat(str(raw_ref).split('.')[0]).replace(tzinfo=ZoneInfo("UTC"))
        run_id = latest_dt.strftime("%Y%m%d_%H")
        iso_str = str(raw_ref).split('.')[0] + "Z"
        ref_str = latest_dt.strftime("%d.%m.%Y %H:00 UTC")
    except Exception as e:
        print(f"-> Hinweis: [{model_name}] Abfrage fehlgeschlagen ({e}).", flush=True)
        return False, None, "latest", None, None

    if latest_known_id == run_id:
        print(f"-> [{model_name}] Lauf {run_id} ist bereits aktuell.", flush=True)
        return False, ref_str, iso_str, run_id, latest_dt

    if model_name == "kenda-ch1":
        print(f"✓ [kenda-ch1] Neue Analyse {run_id} bereitgestellt!", flush=True)
        return True, ref_str, iso_str, run_id, latest_dt

    required_hours = 33 if model_name == "icon-ch1" else (120 if latest_dt.hour in [0, 12] else 45)
    try:
        check_final = ogd_api.Request(collection=model_cfg["collection"], variable="U_10M", ref_time=iso_str, perturbed=False, lead_time=[timedelta(hours=required_hours)])
        ogd_api.get_from_ogd(check_final)
        print(f"✓ [{model_name}] Neuer Lauf {run_id} vollständig bis +{required_hours}h bereit!", flush=True)
        return True, ref_str, iso_str, run_id, latest_dt
    except Exception:
        print(f"-> Warten: [{model_name}] Lauf {run_id} wird noch berechnet (+{required_hours}h fehlt).", flush=True)
        return False, ref_str, iso_str, run_id, latest_dt

def get_dynamic_chunks(total_steps, max_chunks=4):
    k = min(max_chunks, total_steps)
    base, rem = total_steps // k, total_steps % k
    chunks, cur = [], 0
    for i in range(k):
        size = base + (1 if i < rem else 0)
        chunks.append({"chunk": i, "start": cur, "end": cur + size - 1})
        cur += size
    return chunks

def prepare_model_base_site(model_name, ref_time_str, iso_str, run_id, run_dt):
    """Erzeugt Metadaten (times.json, config.json, runs.json) für dist/data und dist-meta/data."""
    model_cfg = config.MODELS_CONFIG[model_name]
    nx, ny = model_cfg.get("nx", config.NX), model_cfg.get("ny", config.NY)
    local_tz = ZoneInfo("Europe/Zurich")
    ref_dt = datetime.fromisoformat(iso_str.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC")) if (iso_str and iso_str not in ["latest", "None"]) else datetime.now(ZoneInfo("UTC"))

    # Schrittzeiten ermitteln
    if model_name == "kenda-ch1":
        times_by_step = [{"step_hours": h, "local_str": (ref_dt - timedelta(hours=4 - h)).astimezone(local_tz).strftime("%d.%m.%Y %H:%M Local")} for h in range(5)]
    else:
        times_by_step = [{"step_hours": h, "local_str": (ref_dt + timedelta(hours=h)).astimezone(local_tz).strftime("%d.%m.%Y %H:%M Local")} for h in config.get_model_step_hours(model_name, ref_dt)]

    num_ens = model_cfg["max_members"] - 1
    member_names = (["Hauptlauf"] + [f"Ens Member {m}" for m in range(1, num_ens + 1)] +
                    ["Median", "Min", "Max", "25% Quantil", "75% Quantil", "Interquantilabstand"]) if num_ens > 0 else ["Hauptlauf"]

    active_cfg = {
        v: {**config.VARIABLES_CONFIG[v], "has_ensemble": (v in model_cfg["ensemble_variables"])}
        for v in model_cfg["active_variables"] if v in config.VARIABLES_CONFIG
    }

    config_data = {
        "model_name": model_name, "run_id": run_id, "model_label": model_cfg["name"],
        "xmin": config.XMIN, "xmax": config.XMAX, "ymin": config.YMIN, "ymax": config.YMAX,
        "nx": nx, "ny": ny, "ref_time_utc": ref_time_str or ref_dt.strftime("%d.%m.%Y %H:00 UTC"),
        "member_names": member_names, "variables": model_cfg["active_variables"],
        "variables_config": active_cfg, "palettes": config.PALETTES_DICT
    }

    for base_folder in ["dist/data", "dist-meta/data"]:
        run_dir = f"{base_folder}/{model_name}/{run_id}"
        os.makedirs(run_dir, exist_ok=True)
        with open(f"{run_dir}/times.json", "w") as f: json.dump(times_by_step, f)
        with open(f"{run_dir}/config.json", "w") as f: json.dump(config_data, f)

        model_dir = f"{base_folder}/{model_name}"
        existing = [r for r in load_existing_runs(model_name) if r.get("id") != run_id]
        new_entry = {"id": run_id, "label": run_dt.strftime("%d.%m. %HZ") if run_dt else run_id, "ref_time_utc": ref_time_str}
        valid_runs = ([new_entry] + existing)[:model_cfg.get("max_runs", 4)]
        with open(f"{model_dir}/runs.json", "w") as f: json.dump(valid_runs, f)

    print(f"✓ Metadaten für [{model_name} / {run_id}] bereitgestellt ({nx}x{ny}, {len(times_by_step)} Schritte)!", flush=True)

def prune_old_runs():
    """Bereinigt historische Läufe und entfernt Einzelmember bei alten Läufen."""
    print("--- PRUNING: Bereinige Läufe & Historie ---", flush=True)
    base_data_dir = "dist/data"

    for m_name, m_cfg in config.MODELS_CONFIG.items():
        model_dir = f"{base_data_dir}/{m_name}"
        if not os.path.exists(model_dir):
            continue

        valid_runs = load_existing_runs(m_name)
        valid_ids = [r["id"] for r in valid_runs]
        latest_id = valid_ids[0] if valid_ids else None
        num_ens = m_cfg["max_members"] - 1

        for entry in os.listdir(model_dir):
            p = os.path.join(model_dir, entry)
            if os.path.isfile(p) and entry != "runs.json":
                os.remove(p)
            elif os.path.isdir(p):
                if entry not in valid_ids:
                    print(f"-> Entferne Lauf älter als Historienfenster ({m_name}): {entry}", flush=True)
                    shutil.rmtree(p, ignore_errors=True)
                elif entry != latest_id and num_ens > 0:
                    pruned = 0
                    for fn in os.listdir(p):
                        if fn.startswith("grid_") and "_m" in fn:
                            try:
                                m_idx = int(fn.split("_m")[1].split("_s")[0])
                                if 1 <= m_idx <= num_ens:
                                    os.remove(os.path.join(p, fn))
                                    pruned += 1
                            except Exception:
                                pass
                    if pruned > 0:
                        print(f"✓ Historischer Lauf {entry} ({m_name}): {pruned} Einzel-Member-Dateien entfernt.", flush=True)

def process_single_local_step(args):
    import stats
    import exporter
    model_name, run_id, local_idx, global_step_idx = args
    step_results = stats.compute_timestep(model_name, SHARED_DATA["weather_data"], local_idx, SHARED_DATA["weights"])
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

    num_steps = end_step - start_step + 1
    print(f"--- STARTE [{model_name} / {run_id}]: Schritte {start_step} bis {end_step} ({num_steps} Schritte) ---", flush=True)
    weather_data = downloader.fetch_weather_data(model_name, start_step, end_step, ref_time_str)
    weights = stats.init_regrid_weights(model_name, weather_data["ref_lon"], weather_data["ref_lat"])

    global SHARED_DATA
    SHARED_DATA = {"weather_data": weather_data, "weights": weights}
    tasks = [(model_name, run_id, i, start_step + i) for i in range(num_steps)]

    ctx = get_context("fork")
    with ctx.Pool(processes=min(4, os.cpu_count() or 2)) as pool:
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
        for sf in ["index.html", "style.css", "app.js"]:
            if os.path.exists(sf):
                shutil.copy(sf, f"dist-meta/{sf}")

        all_chunks = []
        any_new = False

        for m_name, m_cfg in config.MODELS_CONFIG.items():
            is_new, ref_str, iso_str, run_id, run_dt = check_model_new_data(m_name)
            if (is_new or args.force) and run_id:
                any_new = True
                prepare_model_base_site(m_name, ref_str, iso_str, run_id, run_dt)
                total_steps = len(config.get_model_step_hours(m_name, run_dt))
                for c in get_dynamic_chunks(total_steps, max_chunks=m_cfg.get("max_chunks", 4)):
                    all_chunks.append({
                        "model": m_name, "run_id": run_id, "chunk": c["chunk"],
                        "start": c["start"], "end": c["end"], "ref_time": iso_str
                    })

        should_run = any_new or args.force
        if "GITHUB_OUTPUT" in os.environ:
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"should_run={'true' if should_run else 'false'}\n")
                f.write(f"matrix_config={json.dumps({'include': all_chunks})}\n")
        print(f"-> Matrix vorbereitet: {len(all_chunks)} Jobs. should_run={should_run}", flush=True)
        sys.exit(0)

    run_chunk(args.model, args.run_id, args.start_step, args.end_step, args.ref_time)

if __name__ == "__main__":
    main()

import os
import gc
import time
import threading
from datetime import timedelta, datetime
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import xarray as xr
from meteodatalab import ogd_api, grib_decoder, data_source
import config

class SilenceStderr:
    _lock = threading.Lock()
    _refcount = 0
    _save_fd = None
    _null_fd = None

    def __enter__(self):
        with SilenceStderr._lock:
            if SilenceStderr._refcount == 0:
                try:
                    SilenceStderr._null_fd = os.open(os.devnull, os.O_RDWR)
                    SilenceStderr._save_fd = os.dup(2)
                    os.dup2(SilenceStderr._null_fd, 2)
                except Exception:
                    pass
            SilenceStderr._refcount += 1

    def __exit__(self, *_):
        with SilenceStderr._lock:
            SilenceStderr._refcount -= 1
            if SilenceStderr._refcount == 0 and SilenceStderr._save_fd is not None:
                try:
                    os.dup2(SilenceStderr._save_fd, 2)
                    os.close(SilenceStderr._null_fd)
                    os.close(SilenceStderr._save_fd)
                except Exception:
                    pass
                SilenceStderr._save_fd = None
                SilenceStderr._null_fd = None

def safe_squeeze(ds):
    drop_dims = [d for d in ['ref_time', 'z', 'generalVerticalLayer', 'heightAboveGround'] if d in ds.dims and ds.sizes[d] == 1]
    if 'eps' in ds.dims and ds.sizes['eps'] == 1:
        drop_dims.append('eps')
    return ds.squeeze(drop_dims) if drop_dims else ds

def get_hhl_and_weights(collection, hhl_asset, valid_cells=None, target_alts=None):
    if not target_alts:
        return {}
    print(f"-> Lade vertikale Gittergeometrie ({hhl_asset})...", flush=True)
    url_vert = ogd_api.get_collection_asset_url(
        collection_id=f"ch.meteoschweiz.{collection}",
        asset_id=hhl_asset
    )
    for attempt in range(1, 4):
        try:
            with SilenceStderr():
                ds_vert = grib_decoder.load(
                    source=data_source.URLDataSource(urls=[url_vert]),
                    request={"param": "HHL"},
                    geo_coords=lambda uuid: {}
                )
            break
        except Exception as e:
            if attempt == 3:
                raise e
            print(f"⚠️ Netzwerkunterbrechung bei HHL (Versuch {attempt}/3)...", flush=True)
            time.sleep(3)

    hhl_da = ds_vert["HHL"].squeeze()
    if valid_cells is not None:
        hhl_da = hhl_da.isel(cell=valid_cells)
    
    vals = hhl_da.values
    if vals.shape[0] != 81 and vals.shape[-1] == 81:
        vals = np.moveaxis(vals, -1, 0)
    
    num_cells = vals.shape[1]
    col_idx = np.arange(num_cells)
    h_full = 0.5 * (vals[:-1, :] + vals[1:, :])
    hsurf = vals[-1, :]

    alt_prep = {}
    for alt in target_alts:
        is_below = (h_full < alt)
        idx_below = np.argmax(is_below, axis=0)
        idx_above = np.maximum(0, idx_below - 1)

        h_a = h_full[idx_above, col_idx]
        h_b = h_full[idx_below, col_idx]
        dh = np.where((h_a - h_b) == 0, 1e-6, h_a - h_b)
        weight = np.clip((alt - h_b) / dh, 0.0, 1.0).astype(np.float32)
        mask_underground = (hsurf >= alt) | (~np.any(is_below, axis=0))

        alt_prep[alt] = {
            "idx_above": idx_above, "idx_below": idx_below,
            "weight": weight, "mask_underground": mask_underground,
            "col_idx": col_idx
        }

    print(f"✓ HHL geladen & Gewichte für {len(target_alts)} Höhen vorberechnet!", flush=True)
    return alt_prep

def interpolate_fast_precomputed(da_hour, prep):
    idx_above = prep["idx_above"]
    idx_below = prep["idx_below"]
    weight = prep["weight"]
    mask = prep["mask_underground"]
    col_idx = prep["col_idx"]

    z_dim = [d for d in da_hour.dims if d in ['generalVerticalLayer', 'z', 'level']][0]

    if 'eps' in da_hour.dims and da_hour.sizes['eps'] > 1:
        sub = da_hour.squeeze()
        z_axis = sub.dims.index(z_dim)
        eps_axis = sub.dims.index('eps')
        cell_axis = sub.dims.index('cell')
        
        vals_3d = np.transpose(sub.values, (eps_axis, z_axis, cell_axis))
        v_a = vals_3d[:, idx_above, col_idx]
        v_b = vals_3d[:, idx_below, col_idx]
        
        out_interp = (1.0 - weight) * v_b + weight * v_a
        out_interp[:, mask] = np.nan

        coords = {c: da_hour.coords[c] for c in ['eps', 'cell'] if c in da_hour.coords}
        return xr.DataArray(out_interp, dims=['eps', 'cell'], coords=coords)
    else:
        sub = da_hour.squeeze()
        vals_2d = np.moveaxis(sub.values, sub.dims.index(z_dim), 0) if sub.dims[0] != z_dim else sub.values
        v_a = vals_2d[idx_above, col_idx]
        v_b = vals_2d[idx_below, col_idx]
        v_int = (1.0 - weight) * v_b + weight * v_a
        v_int[mask] = np.nan

        coords = {'cell': da_hour.coords['cell']}
        return xr.DataArray(v_int, dims=['cell'], coords=coords)

def fetch_single_2d(collection, var_name, perturbed, ref_time_str, lead_times, valid_cells):
    req = ogd_api.Request(
        collection=collection,
        variable=var_name,
        ref_time=ref_time_str,
        perturbed=perturbed,
        lead_time=lead_times
    )
    for attempt in range(1, 4):
        try:
            with SilenceStderr():
                ds = ogd_api.get_from_ogd(req)
            if valid_cells is not None:
                ds = ds.isel(cell=valid_cells)
            return safe_squeeze(ds)
        except Exception as e:
            if attempt == 3:
                raise RuntimeError(f"Konnte {var_name} ({'Ens' if perturbed else 'HL'}) von {collection} nicht laden: {e}")
            time.sleep(3 * attempt)
    return None

def fetch_dursun_hourly(collection, perturbed, ref_time_str, start_step, end_step, valid_cells):
    actual_start = max(0, start_step - 1)
    fetch_lts = [timedelta(hours=h) for h in range(actual_start, end_step + 1)]
    ds = fetch_single_2d(collection, "DURSUN", perturbed, ref_time_str, fetch_lts, valid_cells)
    
    if ds is not None and "lead_time" in ds.dims and ds.sizes["lead_time"] > 1:
        diff = ds.diff(dim="lead_time")
        diff = xr.where(diff < 0, 0, diff)
        if start_step == 0:
            step0 = ds.isel(lead_time=0) * 0.0
            return xr.concat([step0, diff], dim="lead_time")
        return diff
    return ds

def _fetch_and_slice_single_hour(args):
    collection, var_name, perturbed, ref_time_str, lt, valid_cells, alt_prep, target_alts = args
    req = ogd_api.Request(
        collection=collection,
        variable=var_name,
        ref_time=ref_time_str,
        perturbed=perturbed,
        lead_time=[lt]
    )
    ds_hour = None
    for attempt in range(1, 4):
        try:
            with SilenceStderr():
                ds_hour = ogd_api.get_from_ogd(req)
            break
        except Exception:
            if attempt == 3:
                return None
            time.sleep(2 * attempt)

    if ds_hour is None:
        return None

    if valid_cells is not None:
        ds_hour = ds_hour.isel(cell=valid_cells)

    alt_slices = {}
    for alt in target_alts:
        alt_slices[alt] = interpolate_fast_precomputed(ds_hour, alt_prep[alt])

    del ds_hour
    gc.collect()
    return alt_slices

def fetch_3d_and_slice(collection, var_name, perturbed, ref_time_str, lead_times, valid_cells, alt_prep, target_alts):
    label = f"{var_name} Höhen {[int(a) for a in target_alts]}m ({'Ensemble' if perturbed else 'Hauptlauf'})"
    num_workers = 2 if perturbed else 3
    print(f"-> Verarbeite {label} ({num_workers} Worker)...", flush=True)

    tasks = [
        (collection, var_name, perturbed, ref_time_str, lt, valid_cells, alt_prep, target_alts)
        for lt in lead_times
    ]

    with ThreadPoolExecutor(max_workers=num_workers) as pool:
        hourly_results = list(pool.map(_fetch_and_slice_single_hour, tasks))

    valid_hourly = [hr for hr in hourly_results if hr is not None]
    if not valid_hourly:
        return {}

    results_by_alt = {}
    for alt in target_alts:
        slices = [hr[alt] for hr in valid_hourly if alt in hr]
        if len(slices) > 1:
            results_by_alt[alt] = xr.concat(slices, dim="lead_time")
        elif len(slices) == 1:
            results_by_alt[alt] = slices[0].expand_dims("lead_time")
    return results_by_alt

# ================= DYNAMISCHE ECMWF ZEITSCHRITTE BERECHNEN =================
def get_ecmwf_forecast_hours(run_dt):
    # 00Z / 12Z: bis 240h (10 Tage); 06Z / 18Z: bis 144h (6 Tage)
    is_main_run = (run_dt.hour in [0, 12])
    max_h = 240 if is_main_run else 144

    hours = []
    # 1. Stunde 0 bis 90: stündlich (maximale zeitliche Auflösung!)
    for h in range(0, min(91, max_h + 1)):
        hours.append(h)
    # 2. Stunde 90 bis 144: 3-stündlich
    for h in range(93, min(145, max_h + 1), 3):
        hours.append(h)
    # 3. Stunde 144 bis 240: 6-stündlich (nur bei 00Z/12Z)
    if is_main_run and max_h > 144:
        for h in range(150, max_h + 1, 6):
            hours.append(h)

    return hours

def fetch_ecmwf_wind(start_step, end_step, ref_time_str):
    import requests

    dt = datetime.fromisoformat(ref_time_str.replace("Z", ""))
    all_hours = get_ecmwf_forecast_hours(dt)
    target_hours = all_hours[start_step : end_step + 1]

    days_needed = int(np.ceil((all_hours[-1] + 1) / 24.0))

    print(f"-> Lade natives ECMWF IFS (9 km): Schritte {start_step} bis {end_step} ({len(target_hours)} Zeitpunkte bis +{target_hours[-1]}h)...", flush=True)

    # 42 x 26 = 1092 Punkte über der Schweizer Bounding Box
    lats = np.linspace(config.LAT_MIN, config.LAT_MAX, config.MODELS_CONFIG["ecmwf"]["ny"])
    lons = np.linspace(config.LON_MIN, config.LON_MAX, config.MODELS_CONFIG["ecmwf"]["nx"])
    grid_lon, grid_lat = np.meshgrid(lons, lats)
    flat_lats = grid_lat.ravel()
    flat_lons = grid_lon.ravel()
    total_pts = len(flat_lats)

    batch_size = 250
    all_u = []
    all_v = []
    headers = {"User-Agent": "WeatherDashboard/1.0 (GitHubActions)"}

    for b in range(0, total_pts, batch_size):
        b_lats = flat_lats[b:b+batch_size]
        b_lons = flat_lons[b:b+batch_size]

        lat_str = ",".join([f"{lat:.4f}" for lat in b_lats])
        lon_str = ",".join([f"{lon:.4f}" for lon in b_lons])

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat_str,
            "longitude": lon_str,
            "hourly": "wind_speed_10m,wind_direction_10m",
            "models": "ecmwf_ifs",
            "forecast_days": min(16, max(days_needed, 4))
        }

        success = False
        last_err = ""
        for attempt in range(1, 6):
            try:
                res = requests.get(url, params=params, headers=headers, timeout=40)
                if res.status_code == 200:
                    data = res.json()
                    loc_list = data if isinstance(data, list) else [data]
                    
                    for loc in loc_list:
                        spd = np.array(loc["hourly"]["wind_speed_10m"], dtype=np.float32) / 3.6
                        deg = np.array(loc["hourly"]["wind_direction_10m"], dtype=np.float32)
                        rad = np.deg2rad(deg)
                        u = -spd * np.sin(rad)
                        v = -spd * np.cos(rad)
                        all_u.append(u[target_hours])
                        all_v.append(v[target_hours])
                    
                    success = True
                    break
                elif res.status_code == 429:
                    last_err = "HTTP 429 Rate Limit"
                    time.sleep(5 * attempt)
                else:
                    last_err = f"HTTP {res.status_code}: {res.text[:100]}"
                    time.sleep(3 * attempt)
            except Exception as e:
                last_err = str(e)
                time.sleep(3 * attempt)

        if not success:
            raise RuntimeError(f"Konnte ECMWF Batch {b} nicht abholen ({last_err})")

        time.sleep(0.3)

    u_all = np.array(all_u) # Shape: (points, lead_time)
    v_all = np.array(all_v)

    u_matrix = u_all.T
    v_matrix = v_all.T

    da_u = xr.DataArray(u_matrix, dims=["lead_time", "cell"])
    da_v = xr.DataArray(v_matrix, dims=["lead_time", "cell"])

    print(f"✓ ECMWF IFS 9km ({u_matrix.shape[0]} Schritte, {u_matrix.shape[1]} Punkte) erfolgreich geladen!", flush=True)
    return {
        "surface": {"u_h": da_u, "v_h": da_v},
        "altitude_hl": {},
        "altitude_ens": {},
        "ref_lon": flat_lons,
        "ref_lat": flat_lats
    }

def fetch_weather_data(model_name, start_step, end_step, ref_time_str):
    if model_name == "ecmwf":
        return fetch_ecmwf_wind(start_step, end_step, ref_time_str)

    model_cfg = config.MODELS_CONFIG[model_name]
    collection = model_cfg["collection"]
    active_vars = model_cfg["active_variables"]
    ens_vars = model_cfg["ensemble_variables"]

    lead_times = [timedelta(hours=h) for h in range(start_step, end_step + 1)]

    print(f"1. Pilot-Download [{model_name}]: Hole Referenzgitter aus Stunde 1...", flush=True)
    req_pilot = ogd_api.Request(
        collection=collection,
        variable="U_10M",
        ref_time=ref_time_str,
        perturbed=False,
        lead_time=[timedelta(hours=1)]
    )
    for attempt in range(1, 4):
        try:
            with SilenceStderr():
                ds_pilot = ogd_api.get_from_ogd(req_pilot)
            break
        except Exception as e:
            if attempt == 3:
                raise e
            time.sleep(3)

    lats = ds_pilot.coords['lat'].values
    lons = ds_pilot.coords['lon'].values
    valid_cells = np.where(
        (lats >= config.LAT_MIN) & (lats <= config.LAT_MAX) & 
        (lons >= config.LON_MIN) & (lons <= config.LON_MAX)
    )[0]
    
    ref_lon = ds_pilot.coords['lon'].values[valid_cells]
    ref_lat = ds_pilot.coords['lat'].values[valid_cells]
    del ds_pilot
    gc.collect()

    surface_results = {}
    print(f"2. Lade 2D-Felder für [{model_name}] ({active_vars}) parallel...", flush=True)

    def _fetch_2d_task(key, grib_name, perturbed):
        return key, fetch_single_2d(collection, grib_name, perturbed, ref_time_str, lead_times, valid_cells)

    def _fetch_sun_task(key, perturbed):
        return key, fetch_dursun_hourly(collection, perturbed, ref_time_str, start_step, end_step, valid_cells)

    tasks_2d = []
    if "wind" in active_vars:
        tasks_2d.append(("u_h", "U_10M", False))
        tasks_2d.append(("v_h", "V_10M", False))
        if "wind" in ens_vars:
            tasks_2d.append(("u_e", "U_10M", True))
            tasks_2d.append(("v_e", "V_10M", True))

    if "gust" in active_vars:
        tasks_2d.append(("g_h", "VMAX_10M", False))
        if "gust" in ens_vars:
            tasks_2d.append(("g_e", "VMAX_10M", True))

    if "dbz" in active_vars:
        tasks_2d.append(("dbz_h", "DBZ_CMAX", False))
        if "dbz" in ens_vars:
            tasks_2d.append(("dbz_e", "DBZ_CMAX", True))

    CLOUD_VAR_MAP = {"clct": "CLCT", "clch": "CLCH", "clcm": "CLCM", "clcl": "CLCL"}
    for key, grib_name in CLOUD_VAR_MAP.items():
        if key in active_vars:
            tasks_2d.append((f"{key}_h", grib_name, False))
            if key in ens_vars:
                tasks_2d.append((f"{key}_e", grib_name, True))

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_fetch_2d_task, k, g, p) for k, g, p in tasks_2d]
        if "sun" in active_vars:
            futures.append(pool.submit(_fetch_sun_task, "sun_h", False))
            if "sun" in ens_vars:
                futures.append(pool.submit(_fetch_sun_task, "sun_e", True))

        for f in futures:
            key, ds = f.result()
            surface_results[key] = ds

    hl_altitudes = [v["altitude"] for k, v in config.VARIABLES_CONFIG.items() if v.get("type") == "altitude" and k in active_vars]
    ens_altitudes = [v["altitude"] for k, v in config.VARIABLES_CONFIG.items() if v.get("type") == "altitude" and k in ens_vars]
    all_target_alts = sorted(list(set(hl_altitudes + ens_altitudes)))

    altitude_hl_res = {}
    altitude_ens_res = {}

    if all_target_alts:
        print(f"3. Lade vertikale Höhenwinde [{model_name}] für {all_target_alts}m...", flush=True)
        alt_prep = get_hhl_and_weights(collection, model_cfg["hhl_asset"], valid_cells, all_target_alts)

        with ThreadPoolExecutor(max_workers=2) as pool:
            future_u_hl = pool.submit(fetch_3d_and_slice, collection, "U", False, ref_time_str, lead_times, valid_cells, alt_prep, hl_altitudes)
            future_v_hl = pool.submit(fetch_3d_and_slice, collection, "V", False, ref_time_str, lead_times, valid_cells, alt_prep, hl_altitudes)
            u_hl_by_alt = future_u_hl.result()
            v_hl_by_alt = future_v_hl.result()

        if ens_altitudes:
            u_ens_by_alt = fetch_3d_and_slice(collection, "U", True, ref_time_str, lead_times, valid_cells, alt_prep, ens_altitudes)
            v_ens_by_alt = fetch_3d_and_slice(collection, "V", True, ref_time_str, lead_times, valid_cells, alt_prep, ens_altitudes)
        else:
            u_ens_by_alt, v_ens_by_alt = {}, {}

        altitude_hl_res = {alt: (u_hl_by_alt[alt], v_hl_by_alt[alt]) for alt in hl_altitudes if alt in u_hl_by_alt and alt in v_hl_by_alt}
        altitude_ens_res = {alt: (u_ens_by_alt[alt], v_ens_by_alt[alt]) for alt in ens_altitudes if alt in u_ens_by_alt and alt in v_ens_by_alt}
        del alt_prep
        gc.collect()

    print(f"✓ Datensätze für [{model_name}] bereitgestellt!", flush=True)
    return {
        "surface": surface_results,
        "altitude_hl": altitude_hl_res,
        "altitude_ens": altitude_ens_res,
        "ref_lon": ref_lon,
        "ref_lat": ref_lat
    }

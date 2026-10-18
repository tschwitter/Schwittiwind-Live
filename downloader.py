import os
import gc
import bz2
import time
import tempfile
import threading
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import xarray as xr
import requests
import cfgrib
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

# ================= AROME HD (MÉTÉO-FRANCE) FETCHER =================
def fetch_arome_single_hour(ref_iso, lead_hour):
    urls = [
        f"https://meteofrance-pnt.s3.rbx.io.cloud.ovh.net/pnt/{ref_iso}/arome/001/SP1/arome__001__SP1__{lead_hour:02d}H__{ref_iso}.grib2",
        f"https://object.data.gouv.fr/meteofrance-pnt/pnt/{ref_iso}/arome/001/SP1/arome__001__SP1__{lead_hour:02d}H__{ref_iso}.grib2"
    ]

    resp = None
    for url in urls:
        for attempt in range(1, 4):
            try:
                r = requests.get(url, timeout=30)
                if r.status_code == 200 and len(r.content) > 10000:
                    resp = r
                    break
            except Exception:
                time.sleep(2 * attempt)
        if resp is not None:
            break

    if resp is None:
        print(f"⚠️ AROME Stunde +{lead_hour}h konnte nicht geladen werden.", flush=True)
        return None, None, None, None, None

    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name

    try:
        datasets = cfgrib.open_datasets(tmp_path)
        u10_da, v10_da = None, None
        u_gust_da, v_gust_da, scalar_gust_da = None, None, None

        for ds in datasets:
            if 'u10' in ds:
                u10_da = ds['u10']
            elif '10u' in ds:
                u10_da = ds['10u']
            if 'v10' in ds:
                v10_da = ds['v10']
            elif '10v' in ds:
                v10_da = ds['10v']

            if lead_hour > 0:
                for k in ['fg10', '10fg', 'ff_raf', 'wsgsmax']:
                    if k in ds:
                        scalar_gust_da = ds[k]
                        break
                for ku in ['efg10', 'u10g', 'u_raf']:
                    if ku in ds:
                        u_gust_da = ds[ku]
                        break
                for kv in ['nfg10', 'v10g', 'v_raf']:
                    if kv in ds:
                        v_gust_da = ds[kv]
                        break

        if u10_da is None or v10_da is None:
            for ds in datasets:
                for var_name in ds.data_vars:
                    v = ds[var_name]
                    std_n = getattr(v, 'standard_name', '').lower()
                    if std_n == 'eastward_wind':
                        u10_da = v
                    elif std_n == 'northward_wind':
                        v10_da = v

        if lead_hour > 0 and scalar_gust_da is None and (u_gust_da is None or v_gust_da is None):
            for ds in datasets:
                for var_name in ds.data_vars:
                    v = ds[var_name]
                    long_n = getattr(v, 'long_name', '').lower()
                    grib_n = getattr(v, 'GRIB_name', '').lower()
                    name_comb = f"{long_n} {grib_n}"
                    if 'gust' in name_comb or 'rafale' in name_comb:
                        if 'eastward' in name_comb or ' u ' in name_comb or name_comb.startswith('u '):
                            u_gust_da = v
                        elif 'northward' in name_comb or ' v ' in name_comb or name_comb.startswith('v '):
                            v_gust_da = v
                        elif 'maximum' in name_comb or 'speed' in name_comb:
                            scalar_gust_da = v

        lat_coord = 'latitude' if 'latitude' in u10_da.coords else 'lat'
        lon_coord = 'longitude' if 'longitude' in u10_da.coords else 'lon'

        lat_vals = u10_da[lat_coord].values
        if lat_vals[0] > lat_vals[-1]:
            lat_slice = slice(config.LAT_MAX, config.LAT_MIN)
        else:
            lat_slice = slice(config.LAT_MIN, config.LAT_MAX)

        lon_slice = slice(config.LON_MIN, config.LON_MAX)
        u_sub = u10_da.sel({lat_coord: lat_slice, lon_coord: lon_slice}).values
        v_sub = v10_da.sel({lat_coord: lat_slice, lon_coord: lon_slice}).values

        if lead_hour == 0:
            g_sub = np.full_like(u_sub, np.nan)
        elif scalar_gust_da is not None:
            g_sub = scalar_gust_da.sel({lat_coord: lat_slice, lon_coord: lon_slice}).values
        elif u_gust_da is not None and v_gust_da is not None:
            ug_val = u_gust_da.sel({lat_coord: lat_slice, lon_coord: lon_slice}).values
            vg_val = v_gust_da.sel({lat_coord: lat_slice, lon_coord: lon_slice}).values
            g_sub = np.sqrt(ug_val**2 + vg_val**2)
        else:
            g_sub = np.full_like(u_sub, np.nan)

        sub_lats = u10_da[lat_coord].sel({lat_coord: lat_slice}).values
        sub_lons = u10_da[lon_coord].sel({lon_coord: lon_slice}).values

        glon, glat = np.meshgrid(sub_lons, sub_lats)
        return u_sub.ravel(), v_sub.ravel(), g_sub.ravel(), glon.ravel(), glat.ravel()
    except Exception as e:
        print(f"Fehler beim Dekodieren von AROME GRIB2 (+{lead_hour}h): {e}", flush=True)
        return None, None, None, None, None
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

def fetch_arome_hd_data(start_step, end_step, ref_time_str):
    print(f"-> Lade AROME HD (Wind & Böen) für Schritte {start_step} bis {end_step} ({ref_time_str})...", flush=True)
    lead_hours = list(range(start_step, end_step + 1))

    u_list, v_list, g_list = [], [], []
    ref_lon, ref_lat = None, None

    for h in lead_hours:
        u_arr, v_arr, g_arr, lons, lats = fetch_arome_single_hour(ref_time_str, h)
        if u_arr is not None:
            u_list.append(u_arr)
            v_list.append(v_arr)
            g_list.append(g_arr)
            if ref_lon is None:
                ref_lon = lons
                ref_lat = lats
        else:
            dummy_len = len(ref_lon) if ref_lon is not None else 1000
            u_list.append(np.full(dummy_len, np.nan, dtype=np.float32))
            v_list.append(np.full(dummy_len, np.nan, dtype=np.float32))
            g_list.append(np.full(dummy_len, np.nan, dtype=np.float32))

    u_stack = np.stack(u_list, axis=0)
    v_stack = np.stack(v_list, axis=0)
    g_stack = np.stack(g_list, axis=0)

    u_da = xr.DataArray(u_stack, dims=["lead_time", "cell"])
    v_da = xr.DataArray(v_stack, dims=["lead_time", "cell"])
    g_da = xr.DataArray(g_stack, dims=["lead_time", "cell"])

    return {
        "surface": {
            "u_h": u_da,
            "v_h": v_da,
            "g_h": g_da
        },
        "altitude_hl": {},
        "altitude_ens": {},
        "ref_lon": ref_lon,
        "ref_lat": ref_lat
    }

# ================= DWD ICON-D2 FETCHER =================
def _download_and_extract_dwd_var(cycle_hh, date_ymd, lead_hour, var_name):
    """Lädt eine komprimierte bz2 GRIB2-Datei vom DWD herunter und dekomprimiert sie."""
    url = f"https://opendata.dwd.de/weather/nwp/icon-d2/grib/{cycle_hh}/{var_name}/icon-d2_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{lead_hour:03d}_2d_{var_name}.grib2.bz2"
    for attempt in range(1, 4):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200 and len(r.content) > 1000:
                return bz2.decompress(r.content)
        except Exception:
            time.sleep(2 * attempt)
    return None

def fetch_icond2_single_hour(ref_iso, lead_hour):
    """
    Lädt u_10m und v_10m für eine Stunde von opendata.dwd.de herunter,
    schneidet die Schweizer Bounding Box aus und liefert flache Arrays.
    """
    try:
        ref_dt = datetime.fromisoformat(ref_iso.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    except Exception:
        ref_dt = datetime.now(ZoneInfo("UTC"))

    cycle_hh = ref_dt.strftime("%H")
    date_ymd = ref_dt.strftime("%Y%m%d")

    u_bytes = _download_and_extract_dwd_var(cycle_hh, date_ymd, lead_hour, "u_10m")
    v_bytes = _download_and_extract_dwd_var(cycle_hh, date_ymd, lead_hour, "v_10m")

    if u_bytes is None or v_bytes is None:
        print(f"⚠️ ICON-D2 Stunde +{lead_hour}h konnte nicht geladen werden.", flush=True)
        return None, None, None, None

    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_u, \
         tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_v:
        tmp_u.write(u_bytes)
        tmp_v.write(v_bytes)
        tmp_u_path = tmp_u.name
        tmp_v_path = tmp_v.name

    try:
        with SilenceStderr():
            ds_u = cfgrib.open_dataset(tmp_u_path)
            ds_v = cfgrib.open_dataset(tmp_v_path)

        u_var_name = list(ds_u.data_vars.keys())[0]
        v_var_name = list(ds_v.data_vars.keys())[0]

        lat_coord = 'latitude' if 'latitude' in ds_u.coords else 'lat'
        lon_coord = 'longitude' if 'longitude' in ds_u.coords else 'lon'

        lats = ds_u[lat_coord].values.ravel()
        lons = ds_u[lon_coord].values.ravel()

        mask = (lats >= config.LAT_MIN) & (lats <= config.LAT_MAX) & \
               (lons >= config.LON_MIN) & (lons <= config.LON_MAX)

        u_vals = ds_u[u_var_name].values.ravel()[mask]
        v_vals = ds_v[v_var_name].values.ravel()[mask]
        sub_lons = lons[mask]
        sub_lats = lats[mask]

        ds_u.close()
        ds_v.close()
        return u_vals, v_vals, sub_lons, sub_lats
    except Exception as e:
        print(f"Fehler beim Dekodieren von ICON-D2 (+{lead_hour}h): {e}", flush=True)
        return None, None, None, None
    finally:
        for p in [tmp_u_path, tmp_v_path]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

def fetch_icond2_data(start_step, end_step, ref_time_str):
    print(f"-> Lade ICON-D2 (10m Wind) für Schritte {start_step} bis {end_step} ({ref_time_str})...", flush=True)
    lead_hours = list(range(start_step, end_step + 1))

    u_list, v_list = [], []
    ref_lon, ref_lat = None, None

    for h in lead_hours:
        u_arr, v_arr, lons, lats = fetch_icond2_single_hour(ref_time_str, h)
        if u_arr is not None:
            u_list.append(u_arr)
            v_list.append(v_arr)
            if ref_lon is None:
                ref_lon = lons
                ref_lat = lats
        else:
            dummy_len = len(ref_lon) if ref_lon is not None else 1000
            u_list.append(np.full(dummy_len, np.nan, dtype=np.float32))
            v_list.append(np.full(dummy_len, np.nan, dtype=np.float32))

    u_stack = np.stack(u_list, axis=0)
    v_stack = np.stack(v_list, axis=0)

    u_da = xr.DataArray(u_stack, dims=["lead_time", "cell"])
    v_da = xr.DataArray(v_stack, dims=["lead_time", "cell"])

    return {
        "surface": {
            "u_h": u_da,
            "v_h": v_da
        },
        "altitude_hl": {},
        "altitude_ens": {},
        "ref_lon": ref_lon,
        "ref_lat": ref_lat
    }

def fetch_weather_data(model_name, start_step, end_step, ref_time_str):
    if model_name == "arome":
        return fetch_arome_hd_data(start_step, end_step, ref_time_str)
    if model_name == "icon-d2":
        return fetch_icond2_data(start_step, end_step, ref_time_str)

    model_cfg = config.MODELS_CONFIG[model_name]
    collection = model_cfg["collection"]
    active_vars = model_cfg["active_variables"]
    ens_vars = model_cfg["ensemble_variables"]

    lead_times = [timedelta(hours=h) for h in range(start_step, end_step + 1)]

    # Pilot-Download für Koordinaten
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

    # 3D-Höhenwinde
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

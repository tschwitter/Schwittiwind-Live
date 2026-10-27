import os
import gc
import re
import bz2
import time
import ctypes
import tempfile
import threading
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import xarray as xr
import requests
import cfgrib
import eccodes
from meteodatalab import ogd_api, grib_decoder, data_source
import config

WORKSPACE_TMP = os.path.abspath("tmp_scratch")
os.makedirs(WORKSPACE_TMP, exist_ok=True)
os.environ["TMPDIR"] = WORKSPACE_TMP
tempfile.tempdir = WORKSPACE_TMP

_ICOND2_GRID_CACHE = {}
_OGD_SEMAPHORE = threading.Semaphore(2)

def trim_memory():
    try:
        gc.collect()
        ctypes.CDLL('libc.so.6').malloc_trim(0)
    except Exception:
        pass

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

def retry_call(fn, max_attempts=3, delay_factor=2, err_msg="Operation fehlgeschlagen"):
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            if attempt == max_attempts:
                raise RuntimeError(f"{err_msg}: {e}")
            time.sleep(attempt * delay_factor)
    return None

def safe_squeeze(ds):
    drop_dims = [d for d in ['ref_time', 'z', 'generalVerticalLayer', 'heightAboveGround', 'eps']
                 if d in ds.dims and ds.sizes[d] == 1]
    return ds.squeeze(drop_dims) if drop_dims else ds

# ================= VERTICAL HHL INTERPOLATION =================
def get_hhl_and_weights(collection, hhl_asset, valid_cells=None, target_alts=None):
    if not target_alts:
        return {}
    print(f"-> Lade vertikale Gittergeometrie ({hhl_asset})...", flush=True)
    url_vert = ogd_api.get_collection_asset_url(f"ch.meteoschweiz.{collection}", hhl_asset)

    def _load():
        with SilenceStderr():
            return grib_decoder.load(
                source=data_source.URLDataSource(urls=[url_vert]),
                request={"param": "HHL"},
                geo_coords=lambda uuid: {}
            )

    ds_vert = retry_call(_load, err_msg="Fehler beim Laden von HHL")
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
    all_needed_layers = set()
    for alt in target_alts:
        is_below = (h_full < alt)
        idx_below = np.argmax(is_below, axis=0)
        idx_above = np.maximum(0, idx_below - 1)
        all_needed_layers.update(idx_above.tolist())
        all_needed_layers.update(idx_below.tolist())

        h_a = h_full[idx_above, col_idx]
        h_b = h_full[idx_below, col_idx]
        dh = np.where((h_a - h_b) == 0, 1e-6, h_a - h_b)
        weight = np.clip((alt - h_b) / dh, 0.0, 1.0).astype(np.float32)
        mask_underground = (hsurf >= alt) | (~np.any(is_below, axis=0))

        alt_prep[alt] = {
            "idx_above": idx_above, "idx_below": idx_below,
            "weight": weight, "mask_underground": mask_underground, "col_idx": col_idx
        }

    min_l, max_l = max(0, min(all_needed_layers)), min(vals.shape[0] - 1, max(all_needed_layers))
    alt_prep["_layer_slice"] = (min_l, max_l + 1)
    for alt in target_alts:
        alt_prep[alt]["idx_above_rel"] = alt_prep[alt]["idx_above"] - min_l
        alt_prep[alt]["idx_below_rel"] = alt_prep[alt]["idx_below"] - min_l

    del ds_vert
    trim_memory()
    print(f"✓ HHL geladen & Gewichte für {len(target_alts)} Höhen vorberechnet!", flush=True)
    return alt_prep

def _interpolate_3d(vals_3d, prep, is_ensemble=True):
    idx_a = prep.get("idx_above_rel", prep["idx_above"])
    idx_b = prep.get("idx_below_rel", prep["idx_below"])
    w = prep["weight"]
    mask = prep["mask_underground"]
    col_idx = prep["col_idx"]

    if is_ensemble:
        out = (1.0 - w) * vals_3d[:, idx_b, col_idx] + w * vals_3d[:, idx_a, col_idx]
        out[:, mask] = np.nan
        return out
    out = (1.0 - w) * vals_3d[idx_b, col_idx] + w * vals_3d[idx_a, col_idx]
    out[mask] = np.nan
    return out

def fetch_single_2d(collection, var_name, perturbed, ref_time_str, lead_times, valid_cells):
    req = ogd_api.Request(collection=collection, variable=var_name, ref_time=ref_time_str, perturbed=perturbed, lead_time=lead_times)
    def _fetch():
        with SilenceStderr():
            ds = ogd_api.get_from_ogd(req)
        return safe_squeeze(ds.isel(cell=valid_cells) if valid_cells is not None else ds)
    return retry_call(_fetch, err_msg=f"Konnte {var_name} nicht laden")

def fetch_dursun_hourly(collection, perturbed, ref_time_str, start_step, end_step, valid_cells):
    actual_start = max(0, start_step - 1)
    fetch_lts = [timedelta(hours=h) for h in range(actual_start, end_step + 1)]
    ds = fetch_single_2d(collection, "DURSUN", perturbed, ref_time_str, fetch_lts, valid_cells)
    if ds is not None and "lead_time" in ds.dims and ds.sizes["lead_time"] > 1:
        diff = xr.where(ds.diff(dim="lead_time") < 0, 0, ds.diff(dim="lead_time"))
        return xr.concat([ds.isel(lead_time=0) * 0.0, diff], dim="lead_time") if start_step == 0 else diff
    return ds

def _fetch_and_slice_single_hour(args):
    collection, var_name, perturbed, ref_time_str, lt, valid_cells, alt_prep, target_alts = args
    req = ogd_api.Request(collection=collection, variable=var_name, ref_time=ref_time_str, perturbed=perturbed, lead_time=[lt])
    with _OGD_SEMAPHORE:
        try:
            with SilenceStderr():
                ds_hour = ogd_api.get_from_ogd(req)
        except Exception as e:
            print(f"⚠️ FEHLER beim Laden von 3D {var_name} (lt={lt}): {e}", flush=True)
            return None

        if valid_cells is not None:
            ds_hour = ds_hour.isel(cell=valid_cells)
        sub = ds_hour.squeeze()
        dims_list = list(sub.dims)
        eps_coord = sub.coords['eps'].values if 'eps' in sub.coords else None

        z_dim = next((d for d in dims_list if d in ['generalVerticalLayer', 'z', 'level', 'heightAboveGround']), None)
        if not z_dim:
            return None

        is_ensemble = ('eps' in dims_list and sub.sizes['eps'] > 1)
        if "_layer_slice" in alt_prep:
            l_start, l_end = alt_prep["_layer_slice"]
            sub = sub.isel({z_dim: slice(l_start, l_end)})

        raw_array = np.ascontiguousarray(sub.values, dtype=np.float32)

    if is_ensemble:
        vals_3d = np.transpose(raw_array, (dims_list.index('eps'), dims_list.index(z_dim), dims_list.index('cell')))
    else:
        vals_3d = np.moveaxis(raw_array, dims_list.index(z_dim), 0) if dims_list[0] != z_dim else raw_array

    alt_slices = {}
    for alt in target_alts:
        res = _interpolate_3d(vals_3d, alt_prep[alt], is_ensemble=is_ensemble)
        if is_ensemble:
            alt_slices[alt] = xr.DataArray(res, dims=['eps', 'cell'], coords=({'eps': eps_coord} if eps_coord is not None else None))
        else:
            alt_slices[alt] = xr.DataArray(res, dims=['cell'])

    trim_memory()
    return alt_slices

def fetch_3d_and_slice(collection, var_name, perturbed, ref_time_str, lead_times, valid_cells, alt_prep, target_alts):
    tasks = [(collection, var_name, perturbed, ref_time_str, lt, valid_cells, alt_prep, target_alts) for lt in lead_times]
    with ThreadPoolExecutor(max_workers=3) as pool:
        hourly_results = [hr for hr in pool.map(_fetch_and_slice_single_hour, tasks) if hr is not None]

    if not hourly_results:
        return {}

    results_by_alt = {}
    for alt in target_alts:
        slices = [hr[alt] for hr in hourly_results if alt in hr]
        if len(slices) > 1:
            results_by_alt[alt] = xr.concat(slices, dim="lead_time")
        elif len(slices) == 1:
            results_by_alt[alt] = slices[0].expand_dims("lead_time")
    trim_memory()
    return results_by_alt

# ================= KENDA-CH1 =================
def fetch_kenda_data(start_step, end_step, ref_time_str):
    print(f"-> Lade KENDA-CH1 Analysen für Schritte {start_step}..{end_step} ({ref_time_str})...", flush=True)
    collection = "ogd-analysis-kenda-ch1"
    hhl_asset = config.MODELS_CONFIG["kenda-ch1"]["hhl_asset"]
    active_vars = config.MODELS_CONFIG["kenda-ch1"]["active_variables"]

    try:
        latest_dt = datetime.fromisoformat(ref_time_str.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    except Exception:
        latest_dt = datetime.now(ZoneInfo("UTC"))

    iso_pilot = (latest_dt - timedelta(hours=4 - end_step)).strftime("%Y-%m-%dT%H:00:00Z")
    req_pilot = ogd_api.Request(collection=collection, variable="U_10M", ref_time=iso_pilot, perturbed=False, lead_time=[timedelta(hours=0)])
    ds_pilot = retry_call(lambda: ogd_api.get_from_ogd(req_pilot), err_msg="Fehler beim Pilot-Download (KENDA)")

    lats, lons = ds_pilot.coords['lat'].values, ds_pilot.coords['lon'].values
    valid_cells = np.where((lats >= config.LAT_MIN) & (lats <= config.LAT_MAX) & (lons >= config.LON_MIN) & (lons <= config.LON_MAX))[0]
    ref_lon, ref_lat = lons[valid_cells], lats[valid_cells]
    del ds_pilot

    steps = list(range(start_step, end_step + 1))
    analysis_isos = [(latest_dt - timedelta(hours=4 - s)).strftime("%Y-%m-%dT%H:00:00Z") for s in steps]

    def _fetch_kenda_hour(var_name, lt_hour, iso_t):
        req = ogd_api.Request(collection=collection, variable=var_name, ref_time=iso_t, perturbed=False, lead_time=[timedelta(hours=lt_hour)])
        return retry_call(lambda: safe_squeeze(ogd_api.get_from_ogd(req).isel(cell=valid_cells)), max_attempts=2)

    u_list, v_list, g_list = [], [], []
    clouds = {c: [] for c in ["clct", "clch", "clcm", "clcl"]}
    CLOUD_MAP = {"clct": "CLCT", "clch": "CLCH", "clcm": "CLCM", "clcl": "CLCL"}

    for iso_t in analysis_isos:
        u_list.append(_fetch_kenda_hour("U_10M", 0, iso_t))
        v_list.append(_fetch_kenda_hour("V_10M", 0, iso_t))
        g_list.append(_fetch_kenda_hour("VMAX_10M", 1, iso_t))
        for c_key, grib_name in CLOUD_MAP.items():
            if c_key in active_vars:
                clouds[c_key].append(_fetch_kenda_hour(grib_name, 0, iso_t))

    surface_results = {}
    if all(x is not None for x in u_list): surface_results["u_h"] = xr.concat(u_list, dim="lead_time")
    if all(x is not None for x in v_list): surface_results["v_h"] = xr.concat(v_list, dim="lead_time")
    if all(x is not None for x in g_list): surface_results["g_h"] = xr.concat(g_list, dim="lead_time")
    for c_key in CLOUD_MAP:
        if c_key in active_vars and all(x is not None for x in clouds[c_key]):
            surface_results[f"{c_key}_h"] = xr.concat(clouds[c_key], dim="lead_time")

    altitude_hl_res = {}
    hl_altitudes = [v["altitude"] for k, v in config.VARIABLES_CONFIG.items() if v.get("type") == "altitude" and k in active_vars]
    if hl_altitudes:
        alt_prep = get_hhl_and_weights("ogd-forecasting-icon-ch1", hhl_asset, valid_cells, hl_altitudes)
        u_alt_all = {alt: [] for alt in hl_altitudes}
        v_alt_all = {alt: [] for alt in hl_altitudes}
        for iso_t in analysis_isos:
            res_u = _fetch_and_slice_single_hour((collection, "U", False, iso_t, timedelta(hours=0), valid_cells, alt_prep, hl_altitudes))
            res_v = _fetch_and_slice_single_hour((collection, "V", False, iso_t, timedelta(hours=0), valid_cells, alt_prep, hl_altitudes))
            for alt in hl_altitudes:
                if res_u and alt in res_u: u_alt_all[alt].append(res_u[alt])
                if res_v and alt in res_v: v_alt_all[alt].append(res_v[alt])
        for alt in hl_altitudes:
            if len(u_alt_all[alt]) == len(steps) and len(v_alt_all[alt]) == len(steps):
                altitude_hl_res[alt] = (xr.concat(u_alt_all[alt], dim="lead_time"), xr.concat(v_alt_all[alt], dim="lead_time"))

    trim_memory()
    return {"surface": surface_results, "altitude_hl": altitude_hl_res, "altitude_ens": {}, "ref_lon": ref_lon, "ref_lat": ref_lat}

# ================= AROME HD =================
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
        return None, None, None, None, None

    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name

    try:
        datasets = cfgrib.open_datasets(tmp_path)
        u10_da, v10_da = None, None
        u_gust_da, v_gust_da, scalar_gust_da = None, None, None

        for ds in datasets:
            if 'u10' in ds or '10u' in ds: u10_da = ds.get('u10', ds.get('10u'))
            if 'v10' in ds or '10v' in ds: v10_da = ds.get('v10', ds.get('10v'))
            if lead_hour > 0:
                for k in ['fg10', '10fg', 'ff_raf', 'wsgsmax']:
                    if k in ds: scalar_gust_da = ds[k]; break
                for ku, kv in [('efg10', 'nfg10'), ('u10g', 'v10g'), ('u_raf', 'v_raf')]:
                    if ku in ds and kv in ds:
                        u_gust_da, v_gust_da = ds[ku], ds[kv]; break

        lat_coord = 'latitude' if 'latitude' in u10_da.coords else 'lat'
        lon_coord = 'longitude' if 'longitude' in u10_da.coords else 'lon'
        lat_slice = slice(config.LAT_MAX, config.LAT_MIN) if u10_da[lat_coord].values[0] > u10_da[lat_coord].values[-1] else slice(config.LAT_MIN, config.LAT_MAX)
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

        for ds in datasets:
            ds.close()
        return u_sub.ravel(), v_sub.ravel(), g_sub.ravel(), glon.ravel(), glat.ravel()
    except Exception as e:
        print(f"Fehler beim Dekodieren von AROME GRIB2 (+{lead_hour}h): {e}", flush=True)
        return None, None, None, None, None
    finally:
        if os.path.exists(tmp_path):
            try: os.remove(tmp_path)
            except Exception: pass

def fetch_arome_hd_data(start_step, end_step, ref_time_str):
    print(f"-> Lade AROME HD (Wind & Böen) für Schritte {start_step}..{end_step} ({ref_time_str})...", flush=True)
    u_list, v_list, g_list = [], [], []
    ref_lon, ref_lat = None, None

    for h in range(start_step, end_step + 1):
        u_arr, v_arr, g_arr, lons, lats = fetch_arome_single_hour(ref_time_str, h)
        if u_arr is not None:
            u_list.append(u_arr); v_list.append(v_arr); g_list.append(g_arr)
            if ref_lon is None: ref_lon, ref_lat = lons, lats
        else:
            dummy_len = len(ref_lon) if ref_lon is not None else 1000
            u_list.append(np.full(dummy_len, np.nan, dtype=np.float32))
            v_list.append(np.full(dummy_len, np.nan, dtype=np.float32))
            g_list.append(np.full(dummy_len, np.nan, dtype=np.float32))

    return {
        "surface": {
            "u_h": xr.DataArray(np.stack(u_list, axis=0), dims=["lead_time", "cell"]),
            "v_h": xr.DataArray(np.stack(v_list, axis=0), dims=["lead_time", "cell"]),
            "g_h": xr.DataArray(np.stack(g_list, axis=0), dims=["lead_time", "cell"])
        },
        "altitude_hl": {}, "altitude_ens": {}, "ref_lon": ref_lon, "ref_lat": ref_lat
    }

# ================= DWD ICON-D2 =================
def _download_and_extract_dwd(url):
    def _get():
        r = requests.get(url, timeout=35)
        if r.status_code == 200 and len(r.content) > 1000:
            return bz2.decompress(r.content)
        return None
    return retry_call(_get, max_attempts=3, delay_factor=2)

def _find_dwd_coord_url(cycle_hh, param_name):
    for d_url in [f"https://opendata.dwd.de/weather/nwp/icon-d2/grib/{cycle_hh}/{param_name}/",
                  f"https://opendata.dwd.de/weather/nwp/icon-d2/grib/00/{param_name}/"]:
        try:
            r = requests.get(d_url, timeout=10)
            if r.status_code == 200:
                matches = re.findall(r'href="([^"]*' + param_name + r'[^"]*\.bz2)"', r.text, re.IGNORECASE)
                if matches: return d_url.rstrip('/') + '/' + matches[-1]
        except Exception:
            pass
    return None

def _load_icond2_grid_coords(ref_iso):
    global _ICOND2_GRID_CACHE
    if "valid_indices" in _ICOND2_GRID_CACHE:
        return _ICOND2_GRID_CACHE

    try:
        ref_dt = datetime.fromisoformat(ref_iso.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    except Exception:
        ref_dt = datetime.now(ZoneInfo("UTC"))

    cycle_hh = ref_dt.strftime("%H")
    clat_b = _download_and_extract_dwd(_find_dwd_coord_url(cycle_hh, "clat"))
    clon_b = _download_and_extract_dwd(_find_dwd_coord_url(cycle_hh, "clon"))

    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_lat, \
         tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_lon:
        tmp_lat.write(clat_b); tmp_lon.write(clon_b)
        path_lat, path_lon = tmp_lat.name, tmp_lon.name

    try:
        with SilenceStderr():
            ds_lat, ds_lon = cfgrib.open_dataset(path_lat), cfgrib.open_dataset(path_lon)
        lats = ds_lat[list(ds_lat.data_vars.keys())[0]].values.ravel().astype(np.float64)
        lons = ds_lon[list(ds_lon.data_vars.keys())[0]].values.ravel().astype(np.float64)
        ds_lat.close(); ds_lon.close()

        if np.nanmax(np.abs(lats)) <= 1.6:
            lats, lons = np.rad2deg(lats), np.rad2deg(lons)
        lons = (lons + 180.0) % 360.0 - 180.0

        mask = (lats >= config.LAT_MIN) & (lats <= config.LAT_MAX) & (lons >= config.LON_MIN) & (lons <= config.LON_MAX)
        valid_indices = np.where(mask)[0]

        _ICOND2_GRID_CACHE = {
            "valid_indices": valid_indices,
            "ref_lat": lats[valid_indices].astype(np.float32),
            "ref_lon": lons[valid_indices].astype(np.float32)
        }
        return _ICOND2_GRID_CACHE
    finally:
        for p in [path_lat, path_lon]:
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass

def _extract_grib_array(raw_bytes, valid_indices, is_ensemble=False):
    if raw_bytes is None: return None
    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp:
        tmp.write(raw_bytes); tmp_path = tmp.name
    try:
        with SilenceStderr():
            ds = cfgrib.open_dataset(tmp_path)
        vals = ds[list(ds.data_vars.keys())[0]].values
        ds.close()

        if is_ensemble:
            if vals.ndim == 1: vals = vals[np.newaxis, :]
            elif vals.ndim > 2: vals = np.squeeze(vals)
            if vals.ndim == 1: vals = vals[np.newaxis, :]
            return vals[:, valid_indices].astype(np.float32)
        return vals.ravel()[valid_indices].astype(np.float32)
    except Exception:
        return None
    finally:
        if os.path.exists(tmp_path):
            try: os.remove(tmp_path)
            except Exception: pass

def fetch_icond2_data(start_step, end_step, ref_time_str):
    print(f"-> Lade ICON-D2 (10m Wind & Böen) für Schritte {start_step}..{end_step} ({ref_time_str})...", flush=True)
    grid_info = _load_icond2_grid_coords(ref_time_str)
    valid_indices = grid_info["valid_indices"]
    num_pts = len(valid_indices)

    ref_dt = datetime.fromisoformat(ref_time_str.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    cycle_hh, date_ymd = ref_dt.strftime("%H"), ref_dt.strftime("%Y%m%d")
    base_det = f"https://opendata.dwd.de/weather/nwp/icon-d2/grib/{cycle_hh}"
    base_eps = f"https://opendata.dwd.de/weather/nwp/icon-d2-eps/grib/{cycle_hh}"

    u_h_list, v_h_list, g_h_list, u_e_list, v_e_list, g_e_list = [], [], [], [], [], []
    for h in range(start_step, end_step + 1):
        u_h = _extract_grib_array(_download_and_extract_dwd(f"{base_det}/u_10m/icon-d2_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{h:03d}_2d_u_10m.grib2.bz2"), valid_indices)
        v_h = _extract_grib_array(_download_and_extract_dwd(f"{base_det}/v_10m/icon-d2_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{h:03d}_2d_v_10m.grib2.bz2"), valid_indices)
        g_h = _extract_grib_array(_download_and_extract_dwd(f"{base_det}/vmax_10m/icon-d2_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{h:03d}_2d_vmax_10m.grib2.bz2"), valid_indices) if h > 0 else np.full(num_pts, np.nan, dtype=np.float32)

        u_e = _extract_grib_array(_download_and_extract_dwd(f"{base_eps}/u_10m/icon-d2-eps_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{h:03d}_2d_u_10m.grib2.bz2"), valid_indices, is_ensemble=True)
        v_e = _extract_grib_array(_download_and_extract_dwd(f"{base_eps}/v_10m/icon-d2-eps_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{h:03d}_2d_v_10m.grib2.bz2"), valid_indices, is_ensemble=True)
        g_e = _extract_grib_array(_download_and_extract_dwd(f"{base_eps}/vmax_10m/icon-d2-eps_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{h:03d}_2d_vmax_10m.grib2.bz2"), valid_indices, is_ensemble=True) if h > 0 else np.full((20, num_pts), np.nan, dtype=np.float32)

        u_h_list.append(u_h if u_h is not None else np.full(num_pts, np.nan, dtype=np.float32))
        v_h_list.append(v_h if v_h is not None else np.full(num_pts, np.nan, dtype=np.float32))
        g_h_list.append(g_h if g_h is not None else np.full(num_pts, np.nan, dtype=np.float32))
        u_e_list.append(u_e if u_e is not None else np.full((20, num_pts), np.nan, dtype=np.float32))
        v_e_list.append(v_e if v_e is not None else np.full((20, num_pts), np.nan, dtype=np.float32))
        g_e_list.append(g_e if g_e is not None else np.full((20, num_pts), np.nan, dtype=np.float32))

    return {
        "surface": {
            "u_h": xr.DataArray(np.stack(u_h_list, axis=0), dims=["lead_time", "cell"]),
            "v_h": xr.DataArray(np.stack(v_h_list, axis=0), dims=["lead_time", "cell"]),
            "g_h": xr.DataArray(np.stack(g_h_list, axis=0), dims=["lead_time", "cell"]),
            "u_e": xr.DataArray(np.stack(u_e_list, axis=0), dims=["lead_time", "eps", "cell"]),
            "v_e": xr.DataArray(np.stack(v_e_list, axis=0), dims=["lead_time", "eps", "cell"]),
            "g_e": xr.DataArray(np.stack(g_e_list, axis=0), dims=["lead_time", "eps", "cell"])
        },
        "altitude_hl": {}, "altitude_ens": {}, "ref_lon": grid_info["ref_lon"], "ref_lat": grid_info["ref_lat"]
    }

# ================= ECMWF, AIFS & GFS SUBGRID EXTRACTOR =================
def _extract_swiss_subgrid_fast(grib_path, is_ens=False):
    if not os.path.exists(grib_path) or os.path.getsize(grib_path) < 1000:
        return None, None

    fields = {
        "10u": {}, "10v": {}, "gust": {},
        "clct": {}, "clch": {}, "clcm": {}, "clcl": {}
    }
    ref_lons, ref_lats = None, None

    try:
        with open(grib_path, "rb") as f:
            while True:
                gid = eccodes.codes_grib_new_from_file(f)
                if gid is None:
                    break
                try:
                    param = eccodes.codes_get(gid, "shortName")
                    norm_param = None
                    if param in ["10u", "u10", "u"]:
                        norm_param = "10u"
                    elif param in ["10v", "v10", "v"]:
                        norm_param = "10v"
                    elif param in ["10fg", "10fg3", "10fg6", "fg10", "gust"]:
                        norm_param = "gust"
                    elif param in ["tcc", "clct"]:
                        norm_param = "clct"
                    elif param in ["hcc", "clch"]:
                        norm_param = "clch"
                    elif param in ["mcc", "clcm"]:
                        norm_param = "clcm"
                    elif param in ["lcc", "clcl"]:
                        norm_param = "clcl"

                    if norm_param is None:
                        continue

                    m_num = 0
                    if is_ens:
                        for key in ["perturbationNumber", "number"]:
                            try:
                                m_num = int(eccodes.codes_get(gid, key))
                                break
                            except Exception:
                                pass

                    vals = eccodes.codes_get_values(gid)
                    n_lats, n_lons = int(eccodes.codes_get(gid, "Nj")), int(eccodes.codes_get(gid, "Ni"))
                    la1, lo1 = float(eccodes.codes_get(gid, "latitudeOfFirstGridPointInDegrees")), float(eccodes.codes_get(gid, "longitudeOfFirstGridPointInDegrees"))
                    d_lat, d_lon = float(eccodes.codes_get(gid, "jDirectionIncrementInDegrees")), float(eccodes.codes_get(gid, "iDirectionIncrementInDegrees"))
                    j_scans_pos = int(eccodes.codes_get(gid, "jScansPositively"))

                    matrix = vals.reshape(n_lats, n_lons)
                    lat_arr = la1 + np.arange(n_lats) * d_lat if j_scans_pos == 1 else la1 - np.arange(n_lats) * d_lat
                    lon_arr = (lo1 + np.arange(n_lons) * d_lon + 180.0) % 360.0 - 180.0

                    r_mask = np.where((lat_arr >= config.LAT_MIN) & (lat_arr <= config.LAT_MAX))[0]
                    c_mask = np.where((lon_arr >= config.LON_MIN) & (lon_arr <= config.LON_MAX))[0]
                    
                    if len(r_mask) == 0 or len(c_mask) == 0:
                        r_min, r_max = 0, n_lats
                        c_min, c_max = 0, n_lons
                    else:
                        r_min, r_max = r_mask[0], r_mask[-1] + 1
                        c_min, c_max = c_mask[0], c_mask[-1] + 1

                    sub = matrix[r_min:r_max, c_min:c_max]

                    if ref_lons is None:
                        glon, glat = np.meshgrid(lon_arr[c_min:c_max], lat_arr[r_min:r_max])
                        ref_lons, ref_lats = glon.ravel().astype(np.float32), glat.ravel().astype(np.float32)

                    arr = sub.ravel().astype(np.float32)
                    if norm_param in ["clct", "clch", "clcm", "clcl"] and np.nanmax(arr) <= 1.01:
                        arr = np.clip(arr * 100.0, 0.0, 100.0)

                    fields[norm_param][m_num] = arr
                finally:
                    eccodes.codes_release(gid)

        if not fields["10u"] or not fields["10v"]:
            return None, None

        grid_coords = (ref_lons, ref_lats)
        out_data = {}
        all_pars = ["10u", "10v", "gust", "clct", "clch", "clcm", "clcl"]

        if is_ens:
            target_keys = list(range(1, 51))
            for p_name in all_pars:
                p_dict = fields[p_name]
                if p_dict:
                    fb = next(iter(p_dict.values()))
                    out_data[p_name] = np.array([p_dict.get(k, fb) for k in target_keys], dtype=np.float32)
                else:
                    out_data[p_name] = None
        else:
            for p_name in all_pars:
                p_dict = fields[p_name]
                out_data[p_name] = p_dict[next(iter(p_dict.keys()))] if p_dict else None

        return out_data, grid_coords
    except Exception as e:
        print(f"⚠️ ecCodes Fehler beim Lesen: {e}", flush=True)
        return None, None

# ================= ECMWF IFS =================
def fetch_ecmwf_data(start_step, end_step, ref_time_str):
    from ecmwf.opendata import Client
    print(f"-> Lade ECMWF 0.1° für Index {start_step}..{end_step} ({ref_time_str})...", flush=True)

    ref_dt = datetime.fromisoformat(ref_time_str.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    date_ymd, time_hh = int(ref_dt.strftime("%Y%m%d")), int(ref_dt.strftime("%H"))
    target_steps = config.get_model_step_hours("ecmwf", ref_dt)[start_step : end_step + 1]

    client = None
    for src in ["google", "ecmwf", "azure", "aws"]:
        try:
            client = Client(source=src, model="ifs", resol="0p1")
            break
        except Exception:
            pass

    u_h_list, v_h_list, g_h_list = [], [], []
    c_h_list, ch_h_list, cm_h_list, cl_h_list = [], [], [], []
    u_e_list, v_e_list, g_e_list = [], [], []
    c_e_list, ch_e_list, cm_e_list, cl_e_list = [], [], [], []
    ref_lon, ref_lat = None, None

    for sh in target_steps:
        with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_ctrl, \
             tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_ens:
            path_ctrl, path_ens = tmp_ctrl.name, tmp_ens.name

        ctrl_data, ens_data = None, None
        try:
            client.download(date=date_ymd, time=time_hh, step=sh, type="fc", levtype="sfc", target=path_ctrl)
            ctrl_data, coords_ctrl = _extract_swiss_subgrid_fast(path_ctrl, is_ens=False)
            if ref_lon is None and coords_ctrl:
                ref_lon, ref_lat = coords_ctrl
        except Exception as e:
            print(f"   ⚠️ ECMWF Hauptlauf (+{sh}h): {e}", flush=True)

        try:
            client.download(date=date_ymd, time=time_hh, step=sh, stream="enfo", type="ef", levtype="sfc", target=path_ens)
            ens_data, coords_ens = _extract_swiss_subgrid_fast(path_ens, is_ens=True)
            if ref_lon is None and coords_ens:
                ref_lon, ref_lat = coords_ens
        except Exception as e:
            if sh > 0:
                print(f"   ⚠️ ECMWF Ensemble (+{sh}h): {e}", flush=True)

        for p in [path_ctrl, path_ens]:
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass

        pts = len(ref_lon) if ref_lon is not None else 1352

        u_h  = ctrl_data.get("10u")  if ctrl_data else None
        v_h  = ctrl_data.get("10v")  if ctrl_data else None
        g_h  = ctrl_data.get("gust") if ctrl_data else None
        c_h  = ctrl_data.get("clct") if ctrl_data else None
        ch_h = ctrl_data.get("clch") if ctrl_data else None
        cm_h = ctrl_data.get("clcm") if ctrl_data else None
        cl_h = ctrl_data.get("clcl") if ctrl_data else None

        u_e  = ens_data.get("10u")  if ens_data else None
        v_e  = ens_data.get("10v")  if ens_data else None
        g_e  = ens_data.get("gust") if ens_data else None
        c_e  = ens_data.get("clct") if ens_data else None
        ch_e = ens_data.get("clch") if ens_data else None
        cm_e = ens_data.get("clcm") if ens_data else None
        cl_e = ens_data.get("clcl") if ens_data else None

        if u_e is None and u_h is not None:
            u_e = np.repeat(u_h[np.newaxis, :], 50, axis=0)
            v_e = np.repeat(v_h[np.newaxis, :], 50, axis=0)
        elif u_h is None and u_e is not None:
            u_h, v_h = u_e[0], v_e[0]

        if g_e is None and g_h is not None: g_e = np.repeat(g_h[np.newaxis, :], 50, axis=0)
        elif g_h is None and g_e is not None: g_h = g_e[0]
        if c_e is None and c_h is not None: c_e = np.repeat(c_h[np.newaxis, :], 50, axis=0)
        elif c_h is None and c_e is not None: c_h = c_e[0]
        if ch_e is None and ch_h is not None: ch_e = np.repeat(ch_h[np.newaxis, :], 50, axis=0)
        elif ch_h is None and ch_e is not None: ch_h = ch_e[0]
        if cm_e is None and cm_h is not None: cm_e = np.repeat(cm_h[np.newaxis, :], 50, axis=0)
        elif cm_h is None and cm_e is not None: cm_h = cm_e[0]
        if cl_e is None and cl_h is not None: cl_e = np.repeat(cl_h[np.newaxis, :], 50, axis=0)
        elif cl_h is None and cl_e is not None: cl_h = cl_e[0]

        u_h_list.append(u_h if u_h is not None else np.full(pts, np.nan, dtype=np.float32))
        v_h_list.append(v_h if v_h is not None else np.full(pts, np.nan, dtype=np.float32))
        g_h_list.append(g_h if g_h is not None else np.full(pts, np.nan, dtype=np.float32))
        c_h_list.append(c_h if c_h is not None else np.full(pts, np.nan, dtype=np.float32))
        ch_h_list.append(ch_h if ch_h is not None else np.full(pts, np.nan, dtype=np.float32))
        cm_h_list.append(cm_h if cm_h is not None else np.full(pts, np.nan, dtype=np.float32))
        cl_h_list.append(cl_h if cl_h is not None else np.full(pts, np.nan, dtype=np.float32))

        u_e_list.append(u_e if u_e is not None else np.full((50, pts), np.nan, dtype=np.float32))
        v_e_list.append(v_e if v_e is not None else np.full((50, pts), np.nan, dtype=np.float32))
        g_e_list.append(g_e if g_e is not None else np.full((50, pts), np.nan, dtype=np.float32))
        c_e_list.append(c_e if c_e is not None else np.full((50, pts), np.nan, dtype=np.float32))
        ch_e_list.append(ch_e if ch_e is not None else np.full((50, pts), np.nan, dtype=np.float32))
        cm_e_list.append(cm_e if cm_e is not None else np.full((50, pts), np.nan, dtype=np.float32))
        cl_e_list.append(cl_e if cl_e is not None else np.full((50, pts), np.nan, dtype=np.float32))

    return {
        "surface": {
            "u_h": xr.DataArray(np.stack(u_h_list, axis=0), dims=["lead_time", "cell"]),
            "v_h": xr.DataArray(np.stack(v_h_list, axis=0), dims=["lead_time", "cell"]),
            "g_h": xr.DataArray(np.stack(g_h_list, axis=0), dims=["lead_time", "cell"]),
            "clct_h": xr.DataArray(np.stack(c_h_list, axis=0), dims=["lead_time", "cell"]),
            "clch_h": xr.DataArray(np.stack(ch_h_list, axis=0), dims=["lead_time", "cell"]),
            "clcm_h": xr.DataArray(np.stack(cm_h_list, axis=0), dims=["lead_time", "cell"]),
            "clcl_h": xr.DataArray(np.stack(cl_h_list, axis=0), dims=["lead_time", "cell"]),

            "u_e": xr.DataArray(np.stack(u_e_list, axis=0), dims=["lead_time", "eps", "cell"]),
            "v_e": xr.DataArray(np.stack(v_e_list, axis=0), dims=["lead_time", "eps", "cell"]),
            "g_e": xr.DataArray(np.stack(g_e_list, axis=0), dims=["lead_time", "eps", "cell"]),
            "clct_e": xr.DataArray(np.stack(c_e_list, axis=0), dims=["lead_time", "eps", "cell"]),
            "clch_e": xr.DataArray(np.stack(ch_e_list, axis=0), dims=["lead_time", "eps", "cell"]),
            "clcm_e": xr.DataArray(np.stack(cm_e_list, axis=0), dims=["lead_time", "eps", "cell"]),
            "clcl_e": xr.DataArray(np.stack(cl_e_list, axis=0), dims=["lead_time", "eps", "cell"])
        },
        "altitude_hl": {}, "altitude_ens": {}, "ref_lon": ref_lon, "ref_lat": ref_lat
    }

# ================= ECMWF AIFS =================
def fetch_aifs_data(start_step, end_step, ref_time_str):
    from ecmwf.opendata import Client
    print(f"-> Lade ECMWF AIFS 0.25° KI (10m Wind & 50 Member) für Index {start_step}..{end_step} ({ref_time_str})...", flush=True)

    ref_dt = datetime.fromisoformat(ref_time_str.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    date_ymd, time_hh = int(ref_dt.strftime("%Y%m%d")), int(ref_dt.strftime("%H"))
    target_steps = config.get_model_step_hours("aifs", ref_dt)[start_step : end_step + 1]

    client_single, client_ens = None, None
    for src in ["google", "ecmwf", "azure", "aws"]:
        try:
            client_single = Client(source=src, model="aifs-single", resol="0p25")
            client_ens = Client(source=src, model="aifs-ens", resol="0p25")
            break
        except Exception:
            pass

    u_h_list, v_h_list = [], []
    u_e_list, v_e_list = [], []
    ref_lon, ref_lat = None, None

    for sh in target_steps:
        with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_ctrl, \
             tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_ens:
            path_ctrl, path_ens = tmp_ctrl.name, tmp_ens.name

        ctrl_data, ens_data = None, None
        try:
            client_single.download(date=date_ymd, time=time_hh, step=sh, target=path_ctrl)
            ctrl_data, coords_ctrl = _extract_swiss_subgrid_fast(path_ctrl, is_ens=False)
            if ref_lon is None and coords_ctrl:
                ref_lon, ref_lat = coords_ctrl
        except Exception as e:
            print(f"   ⚠️ AIFS Hauptlauf (+{sh}h): {e}", flush=True)

        try:
            download_ok = False
            for ens_type in ["ef", "pf"]:
                try:
                    client_ens.download(date=date_ymd, time=time_hh, step=sh, stream="enfo", type=ens_type, target=path_ens)
                    download_ok = True
                    break
                except Exception:
                    pass
            if not download_ok:
                client_ens.download(date=date_ymd, time=time_hh, step=sh, target=path_ens)

            ens_data, coords_ens = _extract_swiss_subgrid_fast(path_ens, is_ens=True)
            if ref_lon is None and coords_ens:
                ref_lon, ref_lat = coords_ens
        except Exception as e:
            if sh > 0:
                print(f"   ⚠️ AIFS Ensemble (+{sh}h): {e}", flush=True)

        for p in [path_ctrl, path_ens]:
            if os.path.exists(p):
                try: os.remove(p)
                except Exception: pass

        pts = len(ref_lon) if ref_lon is not None else 1352
        u_h = ctrl_data.get("10u") if ctrl_data else None
        v_h = ctrl_data.get("10v") if ctrl_data else None
        u_e = ens_data.get("10u") if ens_data else None
        v_e = ens_data.get("10v") if ens_data else None

        if u_e is None and u_h is not None:
            u_e = np.repeat(u_h[np.newaxis, :], 50, axis=0)
            v_e = np.repeat(v_h[np.newaxis, :], 50, axis=0)
        elif u_h is None and u_e is not None:
            u_h, v_h = u_e[0], v_e[0]

        u_h_list.append(u_h if u_h is not None else np.full(pts, np.nan, dtype=np.float32))
        v_h_list.append(v_h if v_h is not None else np.full(pts, np.nan, dtype=np.float32))
        u_e_list.append(u_e if u_e is not None else np.full((50, pts), np.nan, dtype=np.float32))
        v_e_list.append(v_e if v_e is not None else np.full((50, pts), np.nan, dtype=np.float32))

    return {
        "surface": {
            "u_h": xr.DataArray(np.stack(u_h_list, axis=0), dims=["lead_time", "cell"]),
            "v_h": xr.DataArray(np.stack(v_h_list, axis=0), dims=["lead_time", "cell"]),
            "u_e": xr.DataArray(np.stack(u_e_list, axis=0), dims=["lead_time", "eps", "cell"]),
            "v_e": xr.DataArray(np.stack(v_e_list, axis=0), dims=["lead_time", "eps", "cell"])
        },
        "altitude_hl": {}, "altitude_ens": {}, "ref_lon": ref_lon, "ref_lat": ref_lat
    }

# ================= NOAA GFS (0.25° VIA NOMADS GRIB-FILTER) =================
def fetch_gfs_single_step(date_ymd, cycle_hh, step_h):
    url = (
        f"https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?"
        f"file=gfs.t{cycle_hh:02d}z.pgrb2.0p25.f{step_h:03d}&lev_10_m_above_ground=on&lev_surface=on&"
        f"var_UGRD=on&var_VGRD=on&var_GUST=on&subregion=&"
        f"leftlon={config.LON_MIN}&rightlon={config.LON_MAX}&toplat={config.LAT_MAX}&bottomlat={config.LAT_MIN}&"
        f"dir=%2Fgfs.{date_ymd}%2F{cycle_hh:02d}%2Fatmos"
    )

    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_f:
        path_tmp = tmp_f.name

    for attempt in range(1, 4):
        try:
            r = requests.get(url, timeout=25)
            if r.status_code == 200 and len(r.content) > 1000:
                with open(path_tmp, "wb") as f:
                    f.write(r.content)
                break
        except Exception:
            time.sleep(2 * attempt)

    data, coords = None, None
    if os.path.exists(path_tmp) and os.path.getsize(path_tmp) > 1000:
        data, coords = _extract_swiss_subgrid_fast(path_tmp, is_ens=False)

    if os.path.exists(path_tmp):
        try: os.remove(path_tmp)
        except Exception: pass

    return data, coords

def fetch_gfs_data(start_step, end_step, ref_time_str):
    print(f"-> Lade NOAA GFS 0.25° (Wind & Böen) für Index {start_step}..{end_step} ({ref_time_str})...", flush=True)
    ref_dt = datetime.fromisoformat(ref_time_str.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    date_ymd, cycle_hh = int(ref_dt.strftime("%Y%m%d")), int(ref_dt.strftime("%H"))
    target_steps = config.get_model_step_hours("gfs", ref_dt)[start_step : end_step + 1]

    u_h_list, v_h_list, g_h_list = [], [], []
    ref_lon, ref_lat = None, None

    for sh in target_steps:
        data, coords = fetch_gfs_single_step(date_ymd, cycle_hh, sh)
        if ref_lon is None and coords:
            ref_lon, ref_lat = coords

        pts = len(ref_lon) if ref_lon is not None else 1352
        u_h = data.get("10u") if data else None
        v_h = data.get("10v") if data else None
        g_h = data.get("gust") if data else None

        u_h_list.append(u_h if u_h is not None else np.full(pts, np.nan, dtype=np.float32))
        v_h_list.append(v_h if v_h is not None else np.full(pts, np.nan, dtype=np.float32))
        g_h_list.append(g_h if g_h is not None else np.full(pts, np.nan, dtype=np.float32))

    return {
        "surface": {
            "u_h": xr.DataArray(np.stack(u_h_list, axis=0), dims=["lead_time", "cell"]),
            "v_h": xr.DataArray(np.stack(v_h_list, axis=0), dims=["lead_time", "cell"]),
            "g_h": xr.DataArray(np.stack(g_h_list, axis=0), dims=["lead_time", "cell"])
        },
        "altitude_hl": {}, "altitude_ens": {}, "ref_lon": ref_lon, "ref_lat": ref_lat
    }

# ================= ALLGEMEINER DISPATCHER =================
def fetch_weather_data(model_name, start_step, end_step, ref_time_str):
    if model_name == "kenda-ch1": return fetch_kenda_data(start_step, end_step, ref_time_str)
    if model_name == "arome":     return fetch_arome_hd_data(start_step, end_step, ref_time_str)
    if model_name == "icon-d2":   return fetch_icond2_data(start_step, end_step, ref_time_str)
    if model_name == "ecmwf":     return fetch_ecmwf_data(start_step, end_step, ref_time_str)
    if model_name == "aifs":      return fetch_aifs_data(start_step, end_step, ref_time_str)
    if model_name == "gfs":       return fetch_gfs_data(start_step, end_step, ref_time_str)

    model_cfg = config.MODELS_CONFIG[model_name]
    collection, active_vars, ens_vars = model_cfg["collection"], model_cfg["active_variables"], model_cfg["ensemble_variables"]
    lead_times = [timedelta(hours=h) for h in range(start_step, end_step + 1)]

    print(f"1. Pilot-Download [{model_name}]: Referenzgitter laden...", flush=True)
    req_pilot = ogd_api.Request(collection=collection, variable="U_10M", ref_time=ref_time_str, perturbed=False, lead_time=[timedelta(hours=1)])
    ds_pilot = retry_call(lambda: ogd_api.get_from_ogd(req_pilot), err_msg="Pilot-Download fehlgeschlagen")

    lats, lons = ds_pilot.coords['lat'].values, ds_pilot.coords['lon'].values
    valid_cells = np.where((lats >= config.LAT_MIN) & (lats <= config.LAT_MAX) & (lons >= config.LON_MIN) & (lons <= config.LON_MAX))[0]
    ref_lon, ref_lat = lons[valid_cells], lats[valid_cells]
    del ds_pilot
    trim_memory()

    surface_results = {}
    tasks_2d = []
    if "wind" in active_vars:
        tasks_2d += [("u_h", "U_10M", False), ("v_h", "V_10M", False)]
        if "wind" in ens_vars: tasks_2d += [("u_e", "U_10M", True), ("v_e", "V_10M", True)]
    if "gust" in active_vars:
        tasks_2d.append(("g_h", "VMAX_10M", False))
        if "gust" in ens_vars: tasks_2d.append(("g_e", "VMAX_10M", True))
    if "dbz" in active_vars:
        tasks_2d.append(("dbz_h", "DBZ_CMAX", False))
        if "dbz" in ens_vars: tasks_2d.append(("dbz_e", "DBZ_CMAX", True))

    for k, grib_n in {"clct": "CLCT", "clch": "CLCH", "clcm": "CLCM", "clcl": "CLCL"}.items():
        if k in active_vars:
            tasks_2d.append((f"{k}_h", grib_n, False))
            if k in ens_vars: tasks_2d.append((f"{k}_e", grib_n, True))

    def _task_exec(t):
        k, grib_n, pert = t
        return k, fetch_single_2d(collection, grib_n, pert, ref_time_str, lead_times, valid_cells)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(_task_exec, t) for t in tasks_2d]
        if "sun" in active_vars:
            futures.append(pool.submit(lambda: ("sun_h", fetch_dursun_hourly(collection, False, ref_time_str, start_step, end_step, valid_cells))))
            if "sun" in ens_vars:
                futures.append(pool.submit(lambda: ("sun_e", fetch_dursun_hourly(collection, True, ref_time_str, start_step, end_step, valid_cells))))
        for f in futures:
            key, ds = f.result()
            surface_results[key] = ds

    trim_memory()

    hl_alts = [v["altitude"] for k, v in config.VARIABLES_CONFIG.items() if v.get("type") == "altitude" and k in active_vars]
    ens_alts = [v["altitude"] for k, v in config.VARIABLES_CONFIG.items() if v.get("type") == "altitude" and k in ens_vars]
    all_target_alts = sorted(list(set(hl_alts + ens_alts)))

    altitude_hl_res, altitude_ens_res = {}, {}
    if all_target_alts:
        print(f"3. Lade vertikale Höhenwinde [{model_name}] für {all_target_alts}m...", flush=True)
        alt_prep = get_hhl_and_weights(collection, model_cfg["hhl_asset"], valid_cells, all_target_alts)

        with ThreadPoolExecutor(max_workers=2) as pool:
            f_u = pool.submit(fetch_3d_and_slice, collection, "U", False, ref_time_str, lead_times, valid_cells, alt_prep, hl_alts)
            f_v = pool.submit(fetch_3d_and_slice, collection, "V", False, ref_time_str, lead_times, valid_cells, alt_prep, hl_alts)
            u_hl, v_hl = f_u.result(), f_v.result()

        u_ens, v_ens = {}, {}
        if ens_alts:
            u_ens = fetch_3d_and_slice(collection, "U", True, ref_time_str, lead_times, valid_cells, alt_prep, ens_alts)
            trim_memory()
            v_ens = fetch_3d_and_slice(collection, "V", True, ref_time_str, lead_times, valid_cells, alt_prep, ens_alts)
            trim_memory()

        altitude_hl_res = {alt: (u_hl[alt], v_hl[alt]) for alt in hl_alts if alt in u_hl and alt in v_hl}
        altitude_ens_res = {alt: (u_ens[alt], v_ens[alt]) for alt in ens_alts if alt in u_ens and alt in v_ens}
        del alt_prep
        trim_memory()

    return {
        "surface": surface_results, "altitude_hl": altitude_hl_res,
        "altitude_ens": altitude_ens_res, "ref_lon": ref_lon, "ref_lat": ref_lat
    }

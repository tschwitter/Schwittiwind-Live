import os
import gc
import re
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

_ICOND2_GRID_CACHE = {}

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
        return None, None, None, None, None

    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name

    try:
        datasets = cfgrib.open_datasets(tmp_path)
        u10_da, v10_da = None, None
        scalar_gust_da = None

        for ds in datasets:
            if 'u10' in ds: u10_da = ds['u10']
            elif '10u' in ds: u10_da = ds['10u']
            if 'v10' in ds: v10_da = ds['v10']
            elif '10v' in ds: v10_da = ds['10v']

            if lead_hour > 0:
                for k in ['fg10', '10fg', 'ff_raf', 'wsgsmax']:
                    if k in ds:
                        scalar_gust_da = ds[k]
                        break

        lat_coord = 'latitude' if 'latitude' in u10_da.coords else 'lat'
        lon_coord = 'longitude' if 'longitude' in u10_da.coords else 'lon'

        lat_vals = u10_da[lat_coord].values
        lat_slice = slice(config.LAT_MAX, config.LAT_MIN) if lat_vals[0] > lat_vals[-1] else slice(config.LAT_MIN, config.LAT_MAX)
        lon_slice = slice(config.LON_MIN, config.LON_MAX)

        u_sub = u10_da.sel({lat_coord: lat_slice, lon_coord: lon_slice}).values
        v_sub = v10_da.sel({lat_coord: lat_slice, lon_coord: lon_slice}).values

        if lead_hour == 0 or scalar_gust_da is None:
            g_sub = np.full_like(u_sub, np.nan)
        else:
            g_sub = scalar_gust_da.sel({lat_coord: lat_slice, lon_coord: lon_slice}).values

        sub_lats = u10_da[lat_coord].sel({lat_coord: lat_slice}).values
        sub_lons = u10_da[lon_coord].sel({lon_coord: lon_slice}).values
        glon, glat = np.meshgrid(sub_lons, sub_lats)

        return u_sub.ravel(), v_sub.ravel(), g_sub.ravel(), glon.ravel(), glat.ravel()
    except Exception:
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
                ref_lon, ref_lat = lons, lats
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
        "altitude_hl": {},
        "altitude_ens": {},
        "ref_lon": ref_lon,
        "ref_lat": ref_lat
    }

# ================= DWD ICON-D2 FETCHER =================
def _download_and_extract_dwd_bytes(url):
    for attempt in range(1, 4):
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200 and len(r.content) > 1000:
                return bz2.decompress(r.content)
        except Exception:
            time.sleep(2 * attempt)
    return None

def _find_dwd_coord_url(cycle_hh, param_name):
    candidate_dirs = [
        f"https://opendata.dwd.de/weather/nwp/icon-d2/grib/{cycle_hh}/{param_name}/",
        f"https://opendata.dwd.de/weather/nwp/icon-d2/grib/00/{param_name}/"
    ]
    for d_url in candidate_dirs:
        try:
            r = requests.get(d_url, timeout=10)
            if r.status_code == 200:
                matches = re.findall(r'href="([^"]*' + param_name + r'[^"]*\.bz2)"', r.text, re.IGNORECASE)
                if matches:
                    return d_url.rstrip('/') + '/' + matches[-1]
        except Exception:
            pass
    return None

def _load_icond2_grid_coords(ref_iso):
    global _ICOND2_GRID_CACHE
    if "valid_indices" in _ICOND2_GRID_CACHE:
        return _ICOND2_GRID_CACHE

    disk_cache = "/tmp/icon_d2_swiss_grid.npz"
    if os.path.exists(disk_cache):
        try:
            data = np.load(disk_cache)
            _ICOND2_GRID_CACHE = {
                "valid_indices": data["valid_indices"],
                "ref_lat": data["ref_lat"],
                "ref_lon": data["ref_lon"]
            }
            return _ICOND2_GRID_CACHE
        except Exception:
            pass

    try:
        ref_dt = datetime.fromisoformat(ref_iso.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    except Exception:
        ref_dt = datetime.now(ZoneInfo("UTC"))

    cycle_hh = ref_dt.strftime("%H")
    url_lat = _find_dwd_coord_url(cycle_hh, "clat")
    url_lon = _find_dwd_coord_url(cycle_hh, "clon")

    clat_bytes = _download_and_extract_dwd_bytes(url_lat)
    clon_bytes = _download_and_extract_dwd_bytes(url_lon)

    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_lat, \
         tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_lon:
        tmp_lat.write(clat_bytes)
        tmp_lon.write(clon_bytes)
        path_lat, path_lon = tmp_lat.name, tmp_lon.name

    try:
        with SilenceStderr():
            ds_lat = cfgrib.open_dataset(path_lat)
            ds_lon = cfgrib.open_dataset(path_lon)

        var_lat = list(ds_lat.data_vars.keys())[0]
        var_lon = list(ds_lon.data_vars.keys())[0]
        lats = ds_lat[var_lat].values.ravel().astype(np.float64)
        lons = ds_lon[var_lon].values.ravel().astype(np.float64)
        ds_lat.close()
        ds_lon.close()

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
        try:
            np.savez_compressed(disk_cache, valid_indices=valid_indices, ref_lat=_ICOND2_GRID_CACHE["ref_lat"], ref_lon=_ICOND2_GRID_CACHE["ref_lon"])
        except Exception:
            pass
        return _ICOND2_GRID_CACHE
    finally:
        for p in [path_lat, path_lon]:
            if os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass

def _extract_grib_array(raw_bytes, valid_indices, is_ensemble=False):
    if raw_bytes is None:
        return None
    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp:
        tmp.write(raw_bytes)
        tmp_path = tmp.name

    try:
        with SilenceStderr():
            ds = cfgrib.open_dataset(tmp_path)
        var_name = list(ds.data_vars.keys())[0]
        vals = ds[var_name].values
        ds.close()

        if is_ensemble:
            if vals.ndim == 1:
                vals = vals[np.newaxis, :]
            elif vals.ndim > 2:
                vals = np.squeeze(vals)
                if vals.ndim == 1:
                    vals = vals[np.newaxis, :]
            return vals[:, valid_indices].astype(np.float32)
        else:
            return vals.ravel()[valid_indices].astype(np.float32)
    except Exception:
        return None
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

def fetch_icond2_single_hour(ref_iso, lead_hour, grid_info):
    try:
        ref_dt = datetime.fromisoformat(ref_iso.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    except Exception:
        ref_dt = datetime.now(ZoneInfo("UTC"))

    cycle_hh = ref_dt.strftime("%H")
    date_ymd = ref_dt.strftime("%Y%m%d")

    base_det = f"https://opendata.dwd.de/weather/nwp/icon-d2/grib/{cycle_hh}"
    base_eps = f"https://opendata.dwd.de/weather/nwp/icon-d2-eps/grib/{cycle_hh}"

    url_u_hl = f"{base_det}/u_10m/icon-d2_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{lead_hour:03d}_2d_u_10m.grib2.bz2"
    url_v_hl = f"{base_det}/v_10m/icon-d2_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{lead_hour:03d}_2d_v_10m.grib2.bz2"
    url_g_hl = f"{base_det}/vmax_10m/icon-d2_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{lead_hour:03d}_2d_vmax_10m.grib2.bz2"

    url_u_ens = f"{base_eps}/u_10m/icon-d2-eps_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{lead_hour:03d}_2d_u_10m.grib2.bz2"
    url_v_ens = f"{base_eps}/v_10m/icon-d2-eps_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{lead_hour:03d}_2d_v_10m.grib2.bz2"
    url_g_ens = f"{base_eps}/vmax_10m/icon-d2-eps_germany_icosahedral_single-level_{date_ymd}{cycle_hh}_{lead_hour:03d}_2d_vmax_10m.grib2.bz2"

    valid_indices = grid_info["valid_indices"]
    num_pts = len(valid_indices)

    u_h = _extract_grib_array(_download_and_extract_dwd_bytes(url_u_hl), valid_indices, is_ensemble=False)
    v_h = _extract_grib_array(_download_and_extract_dwd_bytes(url_v_hl), valid_indices, is_ensemble=False)
    g_h = _extract_grib_array(_download_and_extract_dwd_bytes(url_g_hl), valid_indices, is_ensemble=False) if lead_hour > 0 else np.full(num_pts, np.nan, dtype=np.float32)

    u_e = _extract_grib_array(_download_and_extract_dwd_bytes(url_u_ens), valid_indices, is_ensemble=True)
    v_e = _extract_grib_array(_download_and_extract_dwd_bytes(url_v_ens), valid_indices, is_ensemble=True)
    g_e = _extract_grib_array(_download_and_extract_dwd_bytes(url_g_ens), valid_indices, is_ensemble=True) if lead_hour > 0 else np.full((20, num_pts), np.nan, dtype=np.float32)

    return u_h, v_h, g_h, u_e, v_e, g_e

def fetch_icond2_data(start_step, end_step, ref_time_str):
    print(f"-> Lade ICON-D2 (10m Wind & Böen inkl. 20 Member) für Schritte {start_step} bis {end_step} ({ref_time_str})...", flush=True)
    grid_info = _load_icond2_grid_coords(ref_time_str)
    lead_hours = list(range(start_step, end_step + 1))
    num_pts = len(grid_info["valid_indices"])

    u_h_list, v_h_list, g_h_list = [], [], []
    u_e_list, v_e_list, g_e_list = [], [], []

    for h in lead_hours:
        u_h, v_h, g_h, u_e, v_e, g_e = fetch_icond2_single_hour(ref_time_str, h, grid_info)
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
        "altitude_hl": {},
        "altitude_ens": {},
        "ref_lon": grid_info["ref_lon"],
        "ref_lat": grid_info["ref_lat"]
    }

# ================= ECMWF 0.1° DIRECT-STREAM TURBO FETCHER =================
def _download_stream_fast(url_candidates, target_path):
    """Lädt die GRIB2-Datei in 8-MB-Blöcken mit voller Gigabit-Leitung herunter."""
    for url in url_candidates:
        for attempt in range(1, 3):
            try:
                with requests.get(url, stream=True, timeout=45) as r:
                    if r.status_code == 200:
                        with open(target_path, "wb") as f:
                            for chunk in r.iter_content(chunk_size=8 * 1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                        return True
            except Exception:
                time.sleep(1.5 * attempt)
    return False

def _parse_ecmwf_subgrid(grib_path, is_ens=False):
    """Extrahiert 10u und 10v aus ECMWF 0.1° GRIB2 und schneidet auf die Schweiz zu."""
    try:
        with SilenceStderr():
            datasets = cfgrib.open_datasets(grib_path)
    except Exception:
        return None, None, None, None

    u_da, v_da = None, None
    for ds in datasets:
        if '10u' in ds: u_da = ds['10u']
        elif 'u10' in ds: u_da = ds['u10']
        if '10v' in ds: v_da = ds['10v']
        elif 'v10' in ds: v_da = ds['v10']

    if u_da is None or v_da is None:
        return None, None, None, None

    lat_name = 'latitude' if 'latitude' in u_da.coords else 'lat'
    lon_name = 'longitude' if 'longitude' in u_da.coords else 'lon'

    lat_vals = u_da[lat_name].values
    lat_slice = slice(config.LAT_MAX, config.LAT_MIN) if lat_vals[0] > lat_vals[-1] else slice(config.LAT_MIN, config.LAT_MAX)
    lon_slice = slice(config.LON_MIN, config.LON_MAX)

    u_sub = u_da.sel({lat_name: lat_slice, lon_name: lon_slice}).values
    v_sub = v_da.sel({lat_name: lat_slice, lon_name: lon_slice}).values

    sub_lats = u_da[lat_name].sel({lat_name: lat_slice}).values
    sub_lons = u_da[lon_name].sel({lon_name: lon_slice}).values
    glon, glat = np.meshgrid(sub_lons, sub_lats)

    if is_ens:
        if u_sub.ndim == 3:
            num_m = u_sub.shape[0]
            pts = u_sub.shape[1] * u_sub.shape[2]
            return u_sub.reshape(num_m, pts), v_sub.reshape(num_m, pts), glon.ravel(), glat.ravel()
        else:
            return u_sub.ravel()[np.newaxis, :], v_sub.ravel()[np.newaxis, :], glon.ravel(), glat.ravel()
    else:
        return u_sub.ravel(), v_sub.ravel(), glon.ravel(), glat.ravel()

def fetch_ecmwf_single_step(date_ymd, time_hh, step_hour):
    """Lädt Hauptlauf und alle 50 Ensemble-Member per Turbo-Stream herunter."""
    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_ctrl, \
         tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tmp_ens:
        path_ctrl, path_ens = tmp_ctrl.name, tmp_ens.name

    u_h, v_h = None, None
    u_e, v_e = None, None
    lons, lats = None, None

    hl_stream = "oper" if time_hh in [0, 12] else "scda"
    fn_ctrl = f"{date_ymd}{time_hh:02d}0000-{step_hour}h-{hl_stream}-fc-sfc.grib2"
    fn_ens = f"{date_ymd}{time_hh:02d}0000-{step_hour}h-enfo-ef-sfc.grib2"

    urls_ctrl = [
        f"https://azureopendatastorage.blob.core.windows.net/ecmwf/forecasts/{date_ymd}/{time_hh:02d}z/ifs/0p1/{hl_stream}/{fn_ctrl}",
        f"https://data.ecmwf.int/forecasts/{date_ymd}/{time_hh:02d}z/ifs/0p1/{hl_stream}/{fn_ctrl}"
    ]
    urls_ens = [
        f"https://azureopendatastorage.blob.core.windows.net/ecmwf/forecasts/{date_ymd}/{time_hh:02d}z/ifs/0p1/enfo/{fn_ens}",
        f"https://data.ecmwf.int/forecasts/{date_ymd}/{time_hh:02d}z/ifs/0p1/enfo/{fn_ens}"
    ]

    # 1. Hauptlauf laden
    if _download_stream_fast(urls_ctrl, path_ctrl):
        u_h, v_h, lons, lats = _parse_ecmwf_subgrid(path_ctrl, is_ens=False)

    # 2. 50 Ensemble-Member laden
    if _download_stream_fast(urls_ens, path_ens):
        u_e, v_e, elons, elats = _parse_ecmwf_subgrid(path_ens, is_ens=True)
        if lons is None:
            lons, lats = elons, elats

    # Temporäre Dateien sofort entfernen
    for p in [path_ctrl, path_ens]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass

    if u_h is None and u_e is not None:
        u_h, v_h = u_e[0], v_e[0]

    return u_h, v_h, u_e, v_e, lons, lats

def fetch_ecmwf_data(start_step, end_step, ref_time_str):
    print(f"-> Lade ECMWF 0.1° (10m Wind inkl. 50 Member via High-Speed Stream) für Index {start_step}..{end_step} ({ref_time_str})...", flush=True)

    try:
        ref_dt = datetime.fromisoformat(ref_time_str.replace("Z", "")).replace(tzinfo=ZoneInfo("UTC"))
    except Exception:
        ref_dt = datetime.now(ZoneInfo("UTC"))

    date_ymd = int(ref_dt.strftime("%Y%m%d"))
    time_hh = int(ref_dt.strftime("%H"))

    all_steps = config.get_model_step_hours("ecmwf", ref_dt)
    target_steps = all_steps[start_step : end_step + 1]

    u_h_list, v_h_list = [], []
    u_e_list, v_e_list = [], []
    ref_lon, ref_lat = None, None

    for sh in target_steps:
        t0 = time.time()
        u_h, v_h, u_e, v_e, lons, lats = fetch_ecmwf_single_step(date_ymd, time_hh, sh)
        dt = time.time() - t0
        print(f"   ✓ ECMWF Schritt +{sh}h verarbeitet in {dt:.1f}s", flush=True)

        if u_h is not None and ref_lon is None:
            ref_lon, ref_lat = lons, lats
        elif u_e is not None and ref_lon is None:
            ref_lon, ref_lat = lons, lats

        pts = len(ref_lon) if ref_lon is not None else 1352

        u_h_list.append(u_h if u_h is not None else np.full(pts, np.nan, dtype=np.float32))
        v_h_list.append(v_h if v_h is not None else np.full(pts, np.nan, dtype=np.float32))

        u_e_list.append(u_e if u_e is not None else np.full((50, pts), np.nan, dtype=np.float32))
        v_e_list.append(v_e if v_e is not None else np.full((50, pts), np.nan, dtype=np.float32))

    if ref_lon is None:
        raise RuntimeError("Konnte für ECMWF keine Gitterpunkte extrahieren.")

    return {
        "surface": {
            "u_h": xr.DataArray(np.stack(u_h_list, axis=0), dims=["lead_time", "cell"]),
            "v_h": xr.DataArray(np.stack(v_h_list, axis=0), dims=["lead_time", "cell"]),
            "u_e": xr.DataArray(np.stack(u_e_list, axis=0), dims=["lead_time", "eps", "cell"]),
            "v_e": xr.DataArray(np.stack(v_e_list, axis=0), dims=["lead_time", "eps", "cell"])
        },
        "altitude_hl": {},
        "altitude_ens": {},
        "ref_lon": ref_lon,
        "ref_lat": ref_lat
    }

# ================= ALLGEMEINER DISPATCHER =================
def fetch_weather_data(model_name, start_step, end_step, ref_time_str):
    if model_name == "arome":
        return fetch_arome_hd_data(start_step, end_step, ref_time_str)
    if model_name == "icon-d2":
        return fetch_icond2_data(start_step, end_step, ref_time_str)
    if model_name == "ecmwf":
        return fetch_ecmwf_data(start_step, end_step, ref_time_str)

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
    valid_cells = np.where((lats >= config.LAT_MIN) & (lats <= config.LAT_MAX) & (lons >= config.LON_MIN) & (lons <= config.LON_MAX))[0]
    
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

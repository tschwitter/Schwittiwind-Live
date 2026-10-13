import numpy as np
from scipy.spatial import Delaunay
import config

def init_regrid_weights(source_lons, source_lats):
    print("-> Berechne geometrische Regridding-Gewichte...", flush=True)
    source_points = np.column_stack([source_lons, source_lats])
    
    target_lons = np.linspace(config.XMIN, config.XMAX, config.NX)
    target_lats = np.linspace(config.YMIN, config.YMAX, config.NY)
    grid_lon, grid_lat = np.meshgrid(target_lons, target_lats)
    target_points = np.column_stack([grid_lon.ravel(), grid_lat.ravel()])

    tri = Delaunay(source_points)
    simplex = tri.find_simplex(target_points)
    valid = simplex >= 0
    s = simplex[valid]

    T = tri.transform[s, :2]
    r = tri.transform[s, 2]
    delta = target_points[valid] - r

    b0 = T[:, 0, 0] * delta[:, 0] + T[:, 0, 1] * delta[:, 1]
    b1 = T[:, 1, 0] * delta[:, 0] + T[:, 1, 1] * delta[:, 1]
    b2 = 1.0 - b0 - b1

    vertices = tri.simplices[s]
    print("✓ Geometrische Gewichte erfolgreich im RAM vorbereitet!", flush=True)

    return {
        "v0": vertices[:, 0], "v1": vertices[:, 1], "v2": vertices[:, 2],
        "b0": b0.astype(np.float32), "b1": b1.astype(np.float32), "b2": b2.astype(np.float32),
        "valid": valid, "valid_indices": np.where(valid)[0],
        "grid_lon": grid_lon, "grid_lat": grid_lat
    }

def remap_batch(batch_data, weights):
    """
    Interpoliert ein oder mehrere 1D-Felder in einer einzigen Vektoroperation.
    batch_data: Shape (M, N_cells) oder (N_cells,)
    Rückgabe: Shape (M, NY, NX) bzw. (NY, NX)
    """
    if batch_data is None:
        return np.full((config.NY, config.NX), np.nan, dtype=np.float32)

    is_1d = (batch_data.ndim == 1)
    if is_1d:
        data_2d = batch_data[np.newaxis, :]
    else:
        data_2d = batch_data

    m_count = data_2d.shape[0]
    total_grid = config.NY * config.NX
    out = np.full((m_count, total_grid), np.nan, dtype=np.float32)

    # Vektorisierte Interpolation über alle M Member gleichzeitig
    v0 = data_2d[:, weights["v0"]]
    v1 = data_2d[:, weights["v1"]]
    v2 = data_2d[:, weights["v2"]]

    interp = v0 * weights["b0"] + v1 * weights["b1"] + v2 * weights["b2"]
    out[:, weights["valid_indices"]] = interp

    res = out.reshape(m_count, config.NY, config.NX)
    return res[0] if is_1d else res

def compute_statistics_for_array(all_values, threshold=None):
    """Berechnet Statistiken dynamisch für jede Ensemble-Größe (CH1: 11..16, CH2: 21..26)."""
    s_min = np.nanmin(all_values, axis=0)
    s_max = np.nanmax(all_values, axis=0)
    q25, median, q75 = np.nanpercentile(all_values, (25, 50, 75), axis=0)
    iqr = q75 - q25

    if threshold is not None:
        no_signal = (s_max < threshold) | np.isnan(s_max)
        iqr[no_signal] = np.nan
        s_min[s_min < threshold] = np.nan
        s_max[s_max < threshold] = np.nan
        median[median < threshold] = np.nan
        q25[q25 < threshold] = np.nan
        q75[q75 < threshold] = np.nan

    offset = len(all_values)
    return {
        offset:     {"speed": median, "has_arrows": False},
        offset + 1: {"speed": s_min, "has_arrows": False},
        offset + 2: {"speed": s_max, "has_arrows": False},
        offset + 3: {"speed": q25, "has_arrows": False},
        offset + 4: {"speed": q75, "has_arrows": False},
        offset + 5: {"speed": iqr, "has_arrows": False, "is_iqr": True}
    }

def get_step_slice(da, step_idx):
    if da is None:
        return None
    if "lead_time" in da.dims:
        if step_idx < da.sizes["lead_time"]:
            return da.isel(lead_time=step_idx)
        return None
    return da

def _extract_values_2d(hl_da, ens_da, step_idx):
    """Kombiniert Hauptlauf und alle Ensemble-Member in ein 2D-Array (M, N_cells)."""
    hl_s = get_step_slice(hl_da, step_idx)
    if hl_s is None:
        return None, False

    hl_vals = np.asarray(hl_s.values).squeeze()
    if ens_da is None:
        return hl_vals[np.newaxis, :], False

    ens_s = get_step_slice(ens_da, step_idx)
    if ens_s is None:
        return hl_vals[np.newaxis, :], False

    if "eps" in ens_s.dims and ens_s.dims[0] != "eps":
        ens_s = ens_s.transpose("eps", ...)

    ens_vals = np.asarray(ens_s.values)
    if ens_vals.ndim == 1:
        ens_vals = ens_vals[np.newaxis, :]

    all_vals = np.vstack([hl_vals[np.newaxis, :], ens_vals])
    return all_vals, True

def compute_timestep(model_name, weather_data, step_idx, weights):
    model_cfg = config.MODELS_CONFIG[model_name]
    active_vars = model_cfg["active_variables"]
    ens_vars = model_cfg["ensemble_variables"]

    surface = weather_data["surface"]
    altitude_hl = weather_data["altitude_hl"]
    altitude_ens = weather_data["altitude_ens"]

    step_results = {}

    # 1. 10m Wind
    if "wind" in active_vars and "u_h" in surface and surface["u_h"] is not None:
        has_ens = "wind" in ens_vars
        u_ens = surface.get("u_e") if has_ens else None
        v_ens = surface.get("v_e") if has_ens else None

        all_u, has_e = _extract_values_2d(surface["u_h"], u_ens, step_idx)
        all_v, _ = _extract_values_2d(surface["v_h"], v_ens, step_idx)

        if all_u is not None and all_v is not None:
            gu_all = remap_batch(all_u, weights)
            gv_all = remap_batch(all_v, weights)

            sp_all = np.sqrt(gu_all**2 + gv_all**2) * 3.6
            dr_all = (np.arctan2(gu_all, gv_all) * (180.0 / np.pi)) % 360

            wind_data = {}
            for m in range(len(sp_all)):
                wind_data[m] = {"speed": sp_all[m], "dir": dr_all[m], "has_arrows": True}

            if has_e and len(sp_all) > 1:
                wind_data.update(compute_statistics_for_array(sp_all))
            step_results["wind"] = wind_data

    # 2. Böen (Gust)
    if "gust" in active_vars and "g_h" in surface and surface["g_h"] is not None:
        has_ens = "gust" in ens_vars
        g_ens = surface.get("g_e") if has_ens else None
        all_g, has_e = _extract_values_2d(surface["g_h"], g_ens, step_idx)

        if all_g is not None:
            all_g_remap = remap_batch(all_g, weights) * 3.6
            gust_data = {}
            for m in range(len(all_g_remap)):
                gust_data[m] = {"speed": all_g_remap[m], "has_arrows": False}

            if has_e and len(all_g_remap) > 1:
                gust_data.update(compute_statistics_for_array(all_g_remap))
            step_results["gust"] = gust_data

    # 3. Radar (dBZ)
    if "dbz" in active_vars and "dbz_h" in surface and surface["dbz_h"] is not None:
        has_ens = "dbz" in ens_vars
        dbz_ens = surface.get("dbz_e") if has_ens else None
        all_dbz, has_e = _extract_values_2d(surface["dbz_h"], dbz_ens, step_idx)

        if all_dbz is not None:
            g_dbz = remap_batch(all_dbz, weights)
            np.maximum(0.0, g_dbz, out=g_dbz, where=~np.isnan(g_dbz))

            dbz_data = {}
            for m in range(len(g_dbz)):
                val = g_dbz[m].copy()
                val[val < 7.0] = np.nan
                dbz_data[m] = {"speed": val, "has_arrows": False}

            if has_e and len(g_dbz) > 1:
                dbz_data.update(compute_statistics_for_array(g_dbz, threshold=7.0))
            step_results["dbz"] = dbz_data

    # 4. Sonnenschein (%)
    if "sun" in active_vars and "sun_h" in surface and surface["sun_h"] is not None:
        has_ens = "sun" in ens_vars
        sun_ens = surface.get("sun_e") if has_ens else None
        all_sun, has_e = _extract_values_2d(surface["sun_h"], sun_ens, step_idx)

        if all_sun is not None:
            g_sun = remap_batch(all_sun, weights)
            np.maximum(0.0, g_sun, out=g_sun, where=~np.isnan(g_sun))
            sun_pct = np.clip((g_sun / 3600.0) * 100.0, 0.0, 100.0)

            sun_data = {}
            for m in range(len(sun_pct)):
                val = sun_pct[m].copy()
                val[val < 10.0] = np.nan
                sun_data[m] = {"speed": val, "has_arrows": False}

            if has_e and len(sun_pct) > 1:
                sun_data.update(compute_statistics_for_array(sun_pct, threshold=10.0))
            step_results["sun"] = sun_data

    # 5. Wolken
    CLOUD_KEYS = ["clct", "clch", "clcm", "clcl"]
    for c_key in CLOUD_KEYS:
        if c_key in active_vars and f"{c_key}_h" in surface and surface[f"{c_key}_h"] is not None:
            has_ens = c_key in ens_vars
            c_ens = surface.get(f"{c_key}_e") if has_ens else None
            all_c, has_e = _extract_values_2d(surface[f"{c_key}_h"], c_ens, step_idx)

            if all_c is not None:
                g_c = remap_batch(all_c, weights)
                c_pct = np.clip(g_c, 0.0, 100.0)

                c_data = {}
                for m in range(len(c_pct)):
                    val = c_pct[m].copy()
                    val[val < 10.0] = np.nan
                    c_data[m] = {"speed": val, "has_arrows": False}

                if has_e and len(c_pct) > 1:
                    c_data.update(compute_statistics_for_array(c_pct, threshold=10.0))
                step_results[c_key] = c_data

    # 6. Höhen-Winde
    for var_name, var_cfg in config.VARIABLES_CONFIG.items():
        if var_cfg.get("type") != "altitude" or var_name not in active_vars:
            continue
        alt = var_cfg["altitude"]
        has_ens = var_name in ens_vars

        if alt not in altitude_hl:
            continue

        u_hl, v_hl = altitude_hl[alt]
        u_ens, v_ens = (altitude_ens.get(alt, (None, None))) if has_ens else (None, None)

        all_u, has_e = _extract_values_2d(u_hl, u_ens, step_idx)
        all_v, _ = _extract_values_2d(v_hl, v_ens, step_idx)

        if all_u is not None and all_v is not None:
            gu_all = remap_batch(all_u, weights)
            gv_all = remap_batch(all_v, weights)

            sp_all = np.sqrt(gu_all**2 + gv_all**2) * 3.6
            dr_all = (np.arctan2(gu_all, gv_all) * (180.0 / np.pi)) % 360

            alt_data = {}
            for m in range(len(sp_all)):
                alt_data[m] = {"speed": sp_all[m], "dir": dr_all[m], "has_arrows": True}

            if has_e and len(sp_all) > 1:
                alt_data.update(compute_statistics_for_array(sp_all))
            step_results[var_name] = alt_data

    return step_results

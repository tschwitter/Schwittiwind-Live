import numpy as np
from scipy.spatial import Delaunay
import config

def init_regrid_weights(source_lons, source_lats):
    print("-> Berechne geometrische Regridding-Gewichte einmalig vor...", flush=True)
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

def remap_fast(field, weights):
    raw_vals = field.values if hasattr(field, "values") else field
    vals = np.asarray(raw_vals).squeeze()
    if vals.ndim > 1:
        vals = vals.ravel()

    out = np.full(config.NY * config.NX, np.nan, dtype=np.float32)
    val_v0 = vals[weights["v0"]]
    val_v1 = vals[weights["v1"]]
    val_v2 = vals[weights["v2"]]

    valid_mask = ~(np.isnan(val_v0) | np.isnan(val_v1) | np.isnan(val_v2))
    target_idx = weights["valid_indices"][valid_mask]

    out[target_idx] = (
        weights["b0"][valid_mask] * val_v0[valid_mask] +
        weights["b1"][valid_mask] * val_v1[valid_mask] +
        weights["b2"][valid_mask] * val_v2[valid_mask]
    )
    return out.reshape(config.NY, config.NX)

def compute_statistics_for_array(all_values, threshold=None):
    s_min = np.nanmin(all_values, axis=0)
    s_max = np.nanmax(all_values, axis=0)
    q25, median, q75 = np.nanpercentile(all_values, [25, 50, 75], axis=0)
    iqr = q75 - q25

    if threshold is not None:
        s_min = np.where(s_min < threshold, np.nan, s_min)
        s_max = np.where(s_max < threshold, np.nan, s_max)
        median = np.where(median < threshold, np.nan, median)
        q25 = np.where(q25 < threshold, np.nan, q25)
        q75 = np.where(q75 < threshold, np.nan, q75)

    return {
        11: {"speed": median, "has_arrows": False},
        12: {"speed": s_min, "has_arrows": False},
        13: {"speed": s_max, "has_arrows": False},
        14: {"speed": q25, "has_arrows": False},
        15: {"speed": q75, "has_arrows": False},
        16: {"speed": iqr, "has_arrows": False, "is_iqr": True}
    }

def get_step_slice(da, step_idx):
    if "lead_time" in da.dims:
        return da.isel(lead_time=step_idx)
    return da

def compute_timestep(weather_data, step_idx, weights):
    surface = weather_data["surface"]
    altitude_hl = weather_data["altitude_hl"]
    altitude_ens = weather_data["altitude_ens"]

    step_results = {}

    # 1. 10m Wind & Böen
    if "wind" in config.VARIABLES:
        has_ens = config.VARIABLES_CONFIG["wind"].get("has_ensemble", False)
        u_h, v_h = surface["u_h"], surface["v_h"]
        u_s = get_step_slice(u_h, step_idx)
        v_s = get_step_slice(v_h, step_idx)
        gu = remap_fast(u_s, weights)
        gv = remap_fast(v_s, weights)
        sp = np.sqrt(gu**2 + gv**2) * 3.6
        dr = (np.arctan2(gu, gv) * 180 / np.pi) % 360
        wind_data = {0: {"speed": sp, "dir": dr, "has_arrows": True}}

        if has_ens and "u_e" in surface:
            u_e, v_e = surface["u_e"], surface["v_e"]
            members = u_e.coords['eps'].values
            all_sp = np.zeros((1 + len(members), config.NY, config.NX), dtype=np.float32)
            all_sp[0, :, :] = sp
            for m_i, eps_val in enumerate(members, start=1):
                us_e = get_step_slice(u_e.sel(eps=eps_val), step_idx)
                vs_e = get_step_slice(v_e.sel(eps=eps_val), step_idx)
                gue = remap_fast(us_e, weights)
                gve = remap_fast(vs_e, weights)
                spe = np.sqrt(gue**2 + gve**2) * 3.6
                dre = (np.arctan2(gue, gve) * 180 / np.pi) % 360
                all_sp[m_i, :, :] = spe
                wind_data[m_i] = {"speed": spe, "dir": dre, "has_arrows": True}
            wind_data.update(compute_statistics_for_array(all_sp))
        step_results["wind"] = wind_data

    if "gust" in config.VARIABLES:
        has_ens = config.VARIABLES_CONFIG["gust"].get("has_ensemble", False)
        g_h = surface["g_h"]
        gs_h = get_step_slice(g_h, step_idx)
        sp_g = remap_fast(gs_h, weights) * 3.6
        gust_data = {0: {"speed": sp_g, "has_arrows": False}}

        if has_ens and "g_e" in surface:
            g_e = surface["g_e"]
            members = g_e.coords['eps'].values
            all_g = np.zeros((1 + len(members), config.NY, config.NX), dtype=np.float32)
            all_g[0, :, :] = sp_g
            for m_i, eps_val in enumerate(members, start=1):
                ge_s = get_step_slice(g_e.sel(eps=eps_val), step_idx)
                spe_g = remap_fast(ge_s, weights) * 3.6
                all_g[m_i, :, :] = spe_g
                gust_data[m_i] = {"speed": spe_g, "has_arrows": False}
            gust_data.update(compute_statistics_for_array(all_g))
        step_results["gust"] = gust_data

    # 2. Radar (dBZ)
    if "dbz" in config.VARIABLES:
        has_ens = config.VARIABLES_CONFIG["dbz"].get("has_ensemble", False)
        dbz_h = surface["dbz_h"]
        dbz_s = get_step_slice(dbz_h, step_idx)
        g_dbz = remap_fast(dbz_s, weights)
        dbz_data = {0: {"speed": np.where(g_dbz < 7.0, np.nan, g_dbz), "has_arrows": False}}

        if has_ens and "dbz_e" in surface:
            dbz_e = surface["dbz_e"]
            members = dbz_e.coords['eps'].values
            all_dbz = np.zeros((1 + len(members), config.NY, config.NX), dtype=np.float32)
            all_dbz[0, :, :] = g_dbz
            
            for m_i, eps_val in enumerate(members, start=1):
                d_s = get_step_slice(dbz_e.sel(eps=eps_val), step_idx)
                gd = remap_fast(d_s, weights)
                all_dbz[m_i, :, :] = gd
                dbz_data[m_i] = {"speed": np.where(gd < 7.0, np.nan, gd), "has_arrows": False}
            
            dbz_data.update(compute_statistics_for_array(all_dbz, threshold=7.0))
        step_results["dbz"] = dbz_data

    # 3. Sonnenschein (%)
    if "sun" in config.VARIABLES:
        has_ens = config.VARIABLES_CONFIG["sun"].get("has_ensemble", False)
        sun_h = surface["sun_h"]
        sun_s = get_step_slice(sun_h, step_idx)
        g_sun_sec = remap_fast(sun_s, weights)
        sun_pct = np.clip((g_sun_sec / 3600.0) * 100.0, 0.0, 100.0)
        sun_data = {0: {"speed": np.where(sun_pct < 10.0, np.nan, sun_pct), "has_arrows": False}}

        if has_ens and "sun_e" in surface:
            sun_e = surface["sun_e"]
            members = sun_e.coords['eps'].values
            all_sun = np.zeros((1 + len(members), config.NY, config.NX), dtype=np.float32)
            all_sun[0, :, :] = sun_pct
            
            for m_i, eps_val in enumerate(members, start=1):
                se_s = get_step_slice(sun_e.sel(eps=eps_val), step_idx)
                gs_sec = remap_fast(se_s, weights)
                spct = np.clip((gs_sec / 3600.0) * 100.0, 0.0, 100.0)
                all_sun[m_i, :, :] = spct
                sun_data[m_i] = {"speed": np.where(spct < 10.0, np.nan, spct), "has_arrows": False}
            
            sun_data.update(compute_statistics_for_array(all_sun, threshold=10.0))
        step_results["sun"] = sun_data

    # 4. NEU: Wolken-Variablen (clct, clch, clcm, clcl)
    CLOUD_KEYS = ["clct", "clch", "clcm", "clcl"]
    for c_key in CLOUD_KEYS:
        if c_key in config.VARIABLES and f"{c_key}_h" in surface:
            has_ens = config.VARIABLES_CONFIG[c_key].get("has_ensemble", False)
            c_h = surface[f"{c_key}_h"]
            c_s = get_step_slice(c_h, step_idx)
            g_c = remap_fast(c_s, weights)
            c_pct = np.clip(g_c, 0.0, 100.0)
            c_data = {0: {"speed": np.where(c_pct < 10.0, np.nan, c_pct), "has_arrows": False}}

            if has_ens and f"{c_key}_e" in surface:
                c_e = surface[f"{c_key}_e"]
                members = c_e.coords['eps'].values
                all_c = np.zeros((1 + len(members), config.NY, config.NX), dtype=np.float32)
                all_c[0, :, :] = c_pct
                for m_i, eps_val in enumerate(members, start=1):
                    cs_e = get_step_slice(c_e.sel(eps=eps_val), step_idx)
                    gc_e = remap_fast(cs_e, weights)
                    cp_e = np.clip(gc_e, 0.0, 100.0)
                    all_c[m_i, :, :] = cp_e
                    c_data[m_i] = {"speed": np.where(cp_e < 10.0, np.nan, cp_e), "has_arrows": False}
                c_data.update(compute_statistics_for_array(all_c, threshold=10.0))
            step_results[c_key] = c_data

    # 5. Höhen-Winde
    for var_name, var_cfg in config.VARIABLES_CONFIG.items():
        if var_cfg.get("type") != "altitude" or var_name not in config.VARIABLES:
            continue
        alt = var_cfg["altitude"]
        has_ens = var_cfg.get("has_ensemble", False)
        u_hl, v_hl = altitude_hl[alt]

        u_s = get_step_slice(u_hl, step_idx)
        v_s = get_step_slice(v_hl, step_idx)
        gu = remap_fast(u_s, weights)
        gv = remap_fast(v_s, weights)
        sp = np.sqrt(gu**2 + gv**2) * 3.6
        dr = (np.arctan2(gu, gv) * 180 / np.pi) % 360
        alt_data = {0: {"speed": sp, "dir": dr, "has_arrows": True}}

        if has_ens and alt in altitude_ens:
            u_ens, v_ens = altitude_ens[alt]
            members = u_ens.coords['eps'].values
            all_sp = np.zeros((1 + len(members), config.NY, config.NX), dtype=np.float32)
            all_sp[0, :, :] = sp
            for m_i, eps_val in enumerate(members, start=1):
                ue_s = get_step_slice(u_ens.sel(eps=eps_val), step_idx)
                ve_s = get_step_slice(v_ens.sel(eps=eps_val), step_idx)
                gue = remap_fast(ue_s, weights)
                gve = remap_fast(vs_e, weights)
                spe = np.sqrt(gue**2 + gve**2) * 3.6
                dre = (np.arctan2(gue, gve) * 180 / np.pi) % 360
                all_sp[m_i, :, :] = spe
                alt_data[m_i] = {"speed": spe, "dir": dre, "has_arrows": True}
            alt_data.update(compute_statistics_for_array(all_sp))
        step_results[var_name] = alt_data

    return step_results

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
        "v0": vertices[:, 0],
        "v1": vertices[:, 1],
        "v2": vertices[:, 2],
        "b0": b0.astype(np.float32),
        "b1": b1.astype(np.float32),
        "b2": b2.astype(np.float32),
        "valid": valid,
        "valid_indices": np.where(valid)[0],
        "grid_lon": grid_lon,
        "grid_lat": grid_lat
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

def compute_statistics_for_array(all_speeds):
    s_min = np.nanmin(all_speeds, axis=0)
    s_max = np.nanmax(all_speeds, axis=0)
    q25, median, q75 = np.nanpercentile(all_speeds, [25, 50, 75], axis=0)
    iqr = q75 - q25

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

    u_h, v_h, g_h = surface["u_h"], surface["v_h"], surface["g_h"]
    u_e, v_e, g_e = surface["u_e"], surface["v_e"], surface["g_e"]
    dbz_h, sun_h = surface["dbz_h"], surface["sun_h"]
    dbz_e, sun_e = surface["dbz_e"], surface["sun_e"]

    ensemble_members = u_e.coords['eps'].values
    num_members = 1 + len(ensemble_members)

    step_results = {}

    # 1. BODEN-FELDER (Wind, Böen, dBZ, Sonne)
    all_speeds_wind = np.zeros((num_members, config.NY, config.NX), dtype=np.float32)
    all_speeds_gust = np.zeros((num_members, config.NY, config.NX), dtype=np.float32)
    all_values_dbz  = np.zeros((num_members, config.NY, config.NX), dtype=np.float32)
    all_values_sun  = np.zeros((num_members, config.NY, config.NX), dtype=np.float32)

    wind_data = {}
    gust_data = {}
    dbz_data  = {}
    sun_data  = {}

    for m_idx in range(num_members):
        if m_idx == 0:
            u_s   = get_step_slice(u_h, step_idx)
            v_s   = get_step_slice(v_h, step_idx)
            g_s   = get_step_slice(g_h, step_idx)
            dbz_s = get_step_slice(dbz_h, step_idx)
            sun_s = get_step_slice(sun_h, step_idx)
        else:
            eps_val = ensemble_members[m_idx - 1]
            u_s   = get_step_slice(u_e.sel(eps=eps_val), step_idx)
            v_s   = get_step_slice(v_e.sel(eps=eps_val), step_idx)
            g_s   = get_step_slice(g_e.sel(eps=eps_val), step_idx)
            dbz_s = get_step_slice(dbz_e.sel(eps=eps_val), step_idx)
            sun_s = get_step_slice(sun_e.sel(eps=eps_val), step_idx)

        grid_u   = remap_fast(u_s, weights)
        grid_v   = remap_fast(v_s, weights)
        grid_g   = remap_fast(g_s, weights)
        grid_dbz = remap_fast(dbz_s, weights)
        grid_sun = remap_fast(sun_s, weights)

        # Wind & Böen
        speed_wind = np.sqrt(grid_u**2 + grid_v**2) * 3.6
        dir_wind = (np.arctan2(grid_u, grid_v) * 180 / np.pi) % 360
        all_speeds_wind[m_idx, :, :] = speed_wind
        wind_data[m_idx] = {"speed": speed_wind, "dir": dir_wind, "has_arrows": True}

        speed_gust = grid_g * 3.6
        all_speeds_gust[m_idx, :, :] = speed_gust
        gust_data[m_idx] = {"speed": speed_gust, "has_arrows": False}

        # Radar dBZ (Werte unter 7 sind transparent/kein Regen)
        dbz_val = np.where(grid_dbz < 7.0, np.nan, grid_dbz)
        all_values_dbz[m_idx, :, :] = dbz_val
        dbz_data[m_idx] = {"speed": dbz_val, "has_arrows": False}

        # Sonnenschein % (DURSUN in Sek/h -> / 36 für 0-100 %)
        sun_percent = np.clip(grid_sun / 36.0, 0.0, 100.0)
        sun_percent = np.where(sun_percent < 5.0, np.nan, sun_percent)
        all_values_sun[m_idx, :, :] = sun_percent
        sun_data[m_idx] = {"speed": sun_percent, "has_arrows": False}

    wind_data.update(compute_statistics_for_array(all_speeds_wind))
    gust_data.update(compute_statistics_for_array(all_speeds_gust))
    dbz_data.update(compute_statistics_for_array(all_values_dbz))
    sun_data.update(compute_statistics_for_array(all_values_sun))

    step_results["wind"] = wind_data
    step_results["gust"] = gust_data
    step_results["dbz"]  = dbz_data
    step_results["sun"]  = sun_data

    # 2. HÖHEN-WINDE
    for var_name, var_cfg in config.VARIABLES_CONFIG.items():
        if var_cfg.get("type") != "altitude":
            continue

        alt = var_cfg["altitude"]
        has_ens = var_cfg.get("has_ensemble", False)
        u_hl, v_hl = altitude_hl[alt]

        if has_ens:
            u_ens, v_ens = altitude_ens[alt]
            all_speeds_alt = np.zeros((num_members, config.NY, config.NX), dtype=np.float32)
            alt_data = {}

            for m_idx in range(num_members):
                if m_idx == 0:
                    u_s = get_step_slice(u_hl, step_idx)
                    v_s = get_step_slice(v_hl, step_idx)
                else:
                    eps_val = ensemble_members[m_idx - 1]
                    u_s = get_step_slice(u_ens.sel(eps=eps_val), step_idx)
                    v_s = get_step_slice(v_ens.sel(eps=eps_val), step_idx)

                grid_u = remap_fast(u_s, weights)
                grid_v = remap_fast(v_s, weights)
                speed = np.sqrt(grid_u**2 + grid_v**2) * 3.6
                direction = (np.arctan2(grid_u, grid_v) * 180 / np.pi) % 360
                all_speeds_alt[m_idx, :, :] = speed
                alt_data[m_idx] = {"speed": speed, "dir": direction, "has_arrows": True}

            alt_data.update(compute_statistics_for_array(all_speeds_alt))
            step_results[var_name] = alt_data
        else:
            u_s = get_step_slice(u_hl, step_idx)
            v_s = get_step_slice(v_hl, step_idx)
            grid_u = remap_fast(u_s, weights)
            grid_v = remap_fast(v_s, weights)
            speed = np.sqrt(grid_u**2 + grid_v**2) * 3.6
            direction = (np.arctan2(grid_u, grid_v) * 180 / np.pi) % 360

            step_results[var_name] = {
                0: {"speed": speed, "dir": direction, "has_arrows": True}
            }

    return step_results

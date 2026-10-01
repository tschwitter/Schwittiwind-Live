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
        "grid_lon": grid_lon,
        "grid_lat": grid_lat
    }

def remap_fast(field, weights):
    vals = field.values if hasattr(field, "values") else field
    out = np.full(config.NY * config.NX, np.nan, dtype=np.float32)
    
    # Valid-Maske inklusive NaNs im Quellfeld (z. B. Berge/Fels bei 1500m)
    v0, v1, v2 = weights["v0"], weights["v1"], weights["v2"]
    val_v0, val_v1, val_v2 = vals[v0], vals[v1], vals[v2]
    not_nan = ~np.isnan(val_v0) & ~np.isnan(val_v1) & ~np.isnan(val_v2)

    valid_idx = weights["valid"].copy()
    valid_idx[weights["valid"]] = not_nan

    out[valid_idx] = (
        weights["b0"][not_nan] * val_v0[not_nan] +
        weights["b1"][not_nan] * val_v1[not_nan] +
        weights["b2"][not_nan] * val_v2[not_nan]
    )
    return out.reshape(config.NY, config.NX)

def compute_statistics_for_array(all_speeds):
    median = np.nanmedian(all_speeds, axis=0)
    s_min = np.nanmin(all_speeds, axis=0)
    s_max = np.nanmax(all_speeds, axis=0)
    q25 = np.nanpercentile(all_speeds, 25, axis=0)
    q75 = np.nanpercentile(all_speeds, 75, axis=0)
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

def compute_timestep(u_h, v_h, g_h, u_e, v_e, g_e, u15_h, v15_h, u15_e, v15_e, step_idx, weights):
    ensemble_members = u_e.coords['eps'].values
    num_members = 1 + len(ensemble_members)
    
    all_speeds_wind = np.zeros((num_members, config.NY, config.NX), dtype=np.float32)
    all_speeds_gust = np.zeros((num_members, config.NY, config.NX), dtype=np.float32)
    all_speeds_w15 = np.zeros((num_members, config.NY, config.NX), dtype=np.float32)
    
    wind_data = {}
    gust_data = {}
    wind1500_data = {}

    for m_idx in range(num_members):
        if m_idx == 0:
            u_s = get_step_slice(u_h, step_idx)
            v_s = get_step_slice(v_h, step_idx)
            g_s = get_step_slice(g_h, step_idx)
            u15_s = get_step_slice(u15_h, step_idx)
            v15_s = get_step_slice(v15_h, step_idx)
        else:
            eps_val = ensemble_members[m_idx - 1]
            u_mem = u_e.sel(eps=eps_val) if "eps" in u_e.dims else u_e
            v_mem = v_e.sel(eps=eps_val) if "eps" in v_e.dims else v_e
            g_mem = g_e.sel(eps=eps_val) if "eps" in g_e.dims else g_e
            u15_mem = u15_e.sel(eps=eps_val) if "eps" in u15_e.dims else u15_e
            v15_mem = v15_e.sel(eps=eps_val) if "eps" in v15_e.dims else v15_e
            
            u_s = get_step_slice(u_mem, step_idx)
            v_s = get_step_slice(v_mem, step_idx)
            g_s = get_step_slice(g_mem, step_idx)
            u15_s = get_step_slice(u15_mem, step_idx)
            v15_s = get_step_slice(v15_mem, step_idx)

        # 10m Wind & Böen
        grid_u = remap_fast(u_s, weights)
        grid_v = remap_fast(v_s, weights)
        grid_g = remap_fast(g_s, weights)

        speed_wind = np.sqrt(grid_u**2 + grid_v**2) * 3.6
        dir_wind = (np.arctan2(grid_u, grid_v) * 180 / np.pi) % 360
        all_speeds_wind[m_idx, :, :] = speed_wind
        wind_data[m_idx] = {"speed": speed_wind, "dir": dir_wind, "has_arrows": True}

        speed_gust = grid_g * 3.6
        all_speeds_gust[m_idx, :, :] = speed_gust
        gust_data[m_idx] = {"speed": speed_gust, "has_arrows": False}

        # 1500m Höhenwind
        grid_u15 = remap_fast(u15_s, weights)
        grid_v15 = remap_fast(v15_s, weights)
        speed_w15 = np.sqrt(grid_u15**2 + grid_v15**2) * 3.6
        dir_w15 = (np.arctan2(grid_u15, grid_v15) * 180 / np.pi) % 360
        all_speeds_w15[m_idx, :, :] = speed_w15
        wind1500_data[m_idx] = {"speed": speed_w15, "dir": dir_w15, "has_arrows": True}

    wind_data.update(compute_statistics_for_array(all_speeds_wind))
    gust_data.update(compute_statistics_for_array(all_speeds_gust))
    wind1500_data.update(compute_statistics_for_array(all_speeds_w15))

    return {"wind": wind_data, "gust": gust_data, "wind1500": wind1500_data}

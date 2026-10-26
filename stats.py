import numpy as np
from scipy.spatial import Delaunay
import config

def init_regrid_weights(model_name, source_lons, source_lats):
    """Berechnet Delaunay-Dreiecke und baryzentrische Gewichte auf das Zielgitter."""
    m_cfg = config.MODELS_CONFIG.get(model_name, {})
    nx = m_cfg.get("nx", config.NX)
    ny = m_cfg.get("ny", config.NY)

    print(f"-> Berechne geometrische Regridding-Gewichte [{model_name}: {nx}x{ny}]...", flush=True)
    source_points = np.column_stack([source_lons, source_lats])

    target_lons = np.linspace(config.XMIN, config.XMAX, nx)
    target_lats = np.linspace(config.YMIN, config.YMAX, ny)
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

    print(f"✓ Geometrische Gewichte für [{model_name}] vorbereitet!", flush=True)
    return {
        "nx": nx, "ny": ny,
        "v0": vertices[:, 0], "v1": vertices[:, 1], "v2": vertices[:, 2],
        "b0": b0.astype(np.float32), "b1": b1.astype(np.float32), "b2": b2.astype(np.float32),
        "valid_indices": np.where(valid)[0],
        "grid_lon": grid_lon, "grid_lat": grid_lat
    }

def remap_batch(batch_data, weights):
    """Interpoliert 1D- oder 2D-Arrays (M, N_cells) per Vektoroperation auf (M, NY, NX)."""
    nx, ny = weights["nx"], weights["ny"]
    if batch_data is None:
        return np.full((ny, nx), np.nan, dtype=np.float32)

    is_1d = (batch_data.ndim == 1)
    data_2d = batch_data[np.newaxis, :] if is_1d else batch_data
    m_count = data_2d.shape[0]

    out = np.full((m_count, ny * nx), np.nan, dtype=np.float32)
    v0 = data_2d[:, weights["v0"]]
    v1 = data_2d[:, weights["v1"]]
    v2 = data_2d[:, weights["v2"]]
    out[:, weights["valid_indices"]] = v0 * weights["b0"] + v1 * weights["b1"] + v2 * weights["b2"]

    res = out.reshape(m_count, ny, nx)
    return res[0] if is_1d else res

def compute_statistics_for_array(all_values, threshold=None):
    """Berechnet Median, Min, Max, Quantile und IQR für Member-Arrays."""
    s_min = np.nanmin(all_values, axis=0)
    s_max = np.nanmax(all_values, axis=0)
    q25, median, q75 = np.nanpercentile(all_values, (25, 50, 75), axis=0)
    iqr = q75 - q25

    if threshold is not None:
        no_signal = (s_max < threshold) | np.isnan(s_max)
        iqr[no_signal] = np.nan
        for arr in (s_min, s_max, median, q25, q75):
            arr[arr < threshold] = np.nan

    offset = len(all_values)
    return {
        offset:     {"speed": median, "has_arrows": False},
        offset + 1: {"speed": s_min,  "has_arrows": False},
        offset + 2: {"speed": s_max,  "has_arrows": False},
        offset + 3: {"speed": q25,    "has_arrows": False},
        offset + 4: {"speed": q75,    "has_arrows": False},
        offset + 5: {"speed": iqr,    "has_arrows": False, "is_iqr": True}
    }

def get_step_slice(da, step_idx):
    if da is None:
        return None
    if "lead_time" in da.dims:
        return da.isel(lead_time=step_idx) if step_idx < da.sizes["lead_time"] else None
    return da

def _extract_values_2d(hl_da, ens_da, step_idx):
    """Stapelt Hauptlauf und Member sauber zu einem gemeinsamen Array (M, Cells)."""
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

    return np.vstack([hl_vals[np.newaxis, :], ens_vals]), True

def _process_wind_components(u_all, v_all, weights, has_ens):
    """Konvertiert U- und V-Komponenten in Speed (km/h) und Grad-Richtung."""
    gu = remap_batch(u_all, weights)
    gv = remap_batch(v_all, weights)
    speed = np.sqrt(gu**2 + gv**2) * 3.6
    direction = (np.arctan2(gu, gv) * (180.0 / np.pi)) % 360.0

    res = {m: {"speed": speed[m], "dir": direction[m], "has_arrows": True} for m in range(len(speed))}
    if has_ens and len(speed) > 1:
        res.update(compute_statistics_for_array(speed))
    return res

def _process_scalar_field(all_vals, weights, has_ens, factor=1.0, threshold=None, is_clip_100=False):
    """Generischer Prozessor für skalare Wettergrößen (Böen, dBZ, Sonne, Wolken)."""
    grid = remap_batch(all_vals, weights)
    if factor != 1.0:
        grid = grid * factor
    if is_clip_100:
        grid = np.clip(grid, 0.0, 100.0)
    elif threshold is not None and factor == 1.0:
        np.maximum(0.0, grid, out=grid, where=~np.isnan(grid))

    res = {}
    for m in range(len(grid)):
        val = grid[m].copy()
        if threshold is not None:
            val[val < threshold] = np.nan
        res[m] = {"speed": val, "has_arrows": False}

    if has_ens and len(grid) > 1:
        res.update(compute_statistics_for_array(grid, threshold=threshold))
    return res

def compute_timestep(model_name, weather_data, step_idx, weights):
    """Berechnet alle Parameter eines einzelnen Zeitschritts."""
    model_cfg = config.MODELS_CONFIG[model_name]
    active_vars = model_cfg["active_variables"]
    ens_vars = model_cfg["ensemble_variables"]

    surface = weather_data["surface"]
    altitude_hl = weather_data.get("altitude_hl", {})
    altitude_ens = weather_data.get("altitude_ens", {})
    step_results = {}

    # 1. 10m Wind
    if "wind" in active_vars and "u_h" in surface and surface["u_h"] is not None:
        has_ens = "wind" in ens_vars
        all_u, has_e = _extract_values_2d(surface["u_h"], surface.get("u_e") if has_ens else None, step_idx)
        all_v, _ = _extract_values_2d(surface["v_h"], surface.get("v_e") if has_ens else None, step_idx)
        if all_u is not None and all_v is not None:
            step_results["wind"] = _process_wind_components(all_u, all_v, weights, has_e)

    # 2. Skalare Oberflächenvariablen
    SCALARS = [
        ("gust", "g_h", "g_e", 3.6, None, False),
        ("dbz",  "dbz_h", "dbz_e", 1.0, 7.0, False),
        ("sun",  "sun_h", "sun_e", (100.0 / 3600.0), 10.0, True),
        ("clct", "clct_h", "clct_e", 1.0, 10.0, True),
        ("clch", "clch_h", "clch_e", 1.0, 10.0, True),
        ("clcm", "clcm_h", "clcm_e", 1.0, 10.0, True),
        ("clcl", "clcl_h", "clcl_e", 1.0, 10.0, True),
    ]

    for key, h_key, e_key, factor, threshold, is_pct in SCALARS:
        if key in active_vars and h_key in surface and surface[h_key] is not None:
            has_ens = key in ens_vars
            all_vals, has_e = _extract_values_2d(surface[h_key], surface.get(e_key) if has_ens else None, step_idx)
            if all_vals is not None:
                step_results[key] = _process_scalar_field(all_vals, weights, has_e, factor, threshold, is_pct)

    # 3. Höhenwinde
    for var_name, var_cfg in config.VARIABLES_CONFIG.items():
        if var_cfg.get("type") == "altitude" and var_name in active_vars:
            alt = var_cfg["altitude"]
            if alt in altitude_hl:
                u_hl, v_hl = altitude_hl[alt]
                u_ens, v_ens = altitude_ens.get(alt, (None, None)) if (var_name in ens_vars) else (None, None)
                all_u, has_e = _extract_values_2d(u_hl, u_ens, step_idx)
                all_v, _ = _extract_values_2d(v_hl, v_ens, step_idx)
                if all_u is not None and all_v is not None:
                    step_results[var_name] = _process_wind_components(all_u, all_v, weights, has_e)

    return step_results

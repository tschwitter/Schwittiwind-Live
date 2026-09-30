import numpy as np
from rasterio.crs import CRS
from meteodatalab.operators import regrid
import config

def get_grid_destination():
    return regrid.RegularGrid(CRS.from_epsg(4326), config.NX, config.NY, config.XMIN, config.XMAX, config.YMIN, config.YMAX)

def compute_statistics_for_array(all_speeds):
    """Berechnet Median, Min, Max, 25%, 75% und IQR über die Member-Dimension (axis=0)."""
    median = np.median(all_speeds, axis=0)
    s_min = np.min(all_speeds, axis=0)
    s_max = np.max(all_speeds, axis=0)
    q25 = np.percentile(all_speeds, 25, axis=0)
    q75 = np.percentile(all_speeds, 75, axis=0)
    iqr = q75 - q25

    return {
        11: {"speed": median, "has_arrows": False},
        12: {"speed": s_min, "has_arrows": False},
        13: {"speed": s_max, "has_arrows": False},
        14: {"speed": q25, "has_arrows": False},
        15: {"speed": q75, "has_arrows": False},
        16: {"speed": iqr, "has_arrows": False, "is_iqr": True}
    }

def compute_timestep(u_h, v_h, g_h, u_e, v_e, g_e, step_idx, destination):
    ensemble_members = u_e.coords['eps'].values
    num_members = 1 + len(ensemble_members)
    
    all_speeds_wind = np.zeros((num_members, config.NY, config.NX))
    all_speeds_gust = np.zeros((num_members, config.NY, config.NX))
    
    wind_data = {}
    gust_data = {}

    # 1. Echte Members (0 bis 10) für Wind und Böen berechnen
    for m_idx in range(num_members):
        if m_idx == 0:
            u_s = u_h.isel(lead_time=step_idx)
            v_s = v_h.isel(lead_time=step_idx)
            g_s = g_h.isel(lead_time=step_idx)
        else:
            eps_val = ensemble_members[m_idx - 1]
            u_s = u_e.sel(eps=eps_val).isel(lead_time=step_idx)
            v_s = v_e.sel(eps=eps_val).isel(lead_time=step_idx)
            g_s = g_e.sel(eps=eps_val).isel(lead_time=step_idx)

        # Regridding
        grid_u = regrid.iconremap(u_s, destination).values.reshape(config.NY, config.NX)
        grid_v = regrid.iconremap(v_s, destination).values.reshape(config.NY, config.NX)
        grid_g = regrid.iconremap(g_s, destination).values.reshape(config.NY, config.NX)

        # Windgeschwindigkeit & Richtung
        speed_wind = np.sqrt(grid_u**2 + grid_v**2) * 3.6
        dir_wind = (np.arctan2(grid_u, grid_v) * 180 / np.pi) % 360
        all_speeds_wind[m_idx, :, :] = speed_wind
        wind_data[m_idx] = {"speed": speed_wind, "dir": dir_wind, "has_arrows": True}

        # Böengeschwindigkeit (reiner Skalar in m/s -> km/h, keine Richtung)
        speed_gust = grid_g * 3.6
        all_speeds_gust[m_idx, :, :] = speed_gust
        gust_data[m_idx] = {"speed": speed_gust, "has_arrows": False}

    # 2. Statistiken (11 bis 16) für beide Variablen berechnen
    stats_wind = compute_statistics_for_array(all_speeds_wind)
    stats_gust = compute_statistics_for_array(all_speeds_gust)

    wind_data.update(stats_wind)
    gust_data.update(stats_gust)

    return {"wind": wind_data, "gust": gust_data}

import numpy as np
from rasterio.crs import CRS
from meteodatalab.operators import regrid
import config

def get_grid_destination():
    return regrid.RegularGrid(CRS.from_epsg(4326), config.NX, config.NY, config.XMIN, config.XMAX, config.YMIN, config.YMAX)

def compute_timestep(u_haupt, v_haupt, u_ens, v_ens, step_idx, destination):
    ensemble_members = u_ens.coords['eps'].values
    num_members = 1 + len(ensemble_members)
    all_speeds = np.zeros((num_members, config.NY, config.NX))
    member_data = {}

    # 1. Berechne 11 echte Members
    for m_idx in range(num_members):
        if m_idx == 0:
            u_step = u_haupt.isel(lead_time=step_idx)
            v_step = v_haupt.isel(lead_time=step_idx)
        else:
            eps_val = ensemble_members[m_idx - 1]
            u_step = u_ens.sel(eps=eps_val).isel(lead_time=step_idx)
            v_step = v_ens.sel(eps=eps_val).isel(lead_time=step_idx)

        grid_u = regrid.iconremap(u_step, destination).values.reshape(config.NY, config.NX)
        grid_v = regrid.iconremap(v_step, destination).values.reshape(config.NY, config.NX)

        speed = np.sqrt(grid_u**2 + grid_v**2) * 3.6
        direction = (np.arctan2(grid_u, grid_v) * 180 / np.pi) % 360
        all_speeds[m_idx, :, :] = speed

        member_data[m_idx] = {"speed": speed, "dir": direction, "has_arrows": True}

    # 2. Berechne die 6 Statistik-Karten (neue Reihenfolge!)
    median = np.median(all_speeds, axis=0)
    q25 = np.percentile(all_speeds, 25, axis=0)
    q75 = np.percentile(all_speeds, 75, axis=0)
    iqr = q75 - q25
    s_min = np.min(all_speeds, axis=0)
    s_max = np.max(all_speeds, axis=0)

    member_data[11] = {"speed": median, "has_arrows": False}
    member_data[12] = {"speed": s_min, "has_arrows": False}
    member_data[13] = {"speed": s_max, "has_arrows": False}
    member_data[14] = {"speed": q25, "has_arrows": False}
    member_data[15] = {"speed": q75, "has_arrows": False}
    member_data[16] = {"speed": iqr, "has_arrows": False, "is_iqr": True}

    return member_data

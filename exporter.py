import gzip
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import geojsoncontour
import config

# Prozess-lokaler Cache für die Figur
CURRENT_FIG = None
CURRENT_AX = None

def get_render_axes():
    global CURRENT_FIG, CURRENT_AX
    if CURRENT_AX is None:
        CURRENT_FIG, CURRENT_AX = plt.subplots()
    return CURRENT_AX

def export_variable_step(var_name, m_idx, step_idx, data):
    ax = get_render_axes()
    ax.clear()
    
    speed = data["speed"]
    
    lon_1d = np.linspace(config.XMIN, config.XMAX, config.NX)
    lat_1d = np.linspace(config.YMIN, config.YMAX, config.NY)
    grid_lon, grid_lat = np.meshgrid(lon_1d, lat_1d)

    if data.get("is_iqr", False):
        contourf = ax.contourf(grid_lon, grid_lat, speed, levels=config.IQR_LEVELS, colors=config.IQR_COLORS, alpha=0.55)
    else:
        contourf = ax.contourf(grid_lon, grid_lat, speed, levels=config.LEVELS, colors=config.COLORS, alpha=0.55)

    raw_geojson = geojsoncontour.contourf_to_geojson(contourf=contourf, ndigits=3)
    with gzip.open(f"dist/data/contours_{var_name}_m{m_idx}_s{step_idx}.json.gz", "wt", encoding="utf-8") as f:
        f.write(raw_geojson)

    # Pfeile nur für Wind mit Richtung exportieren
    if data.get("has_arrows", False) and "dir" in data:
        direction = data["dir"]
        s_flat = np.where(np.isnan(speed) | (speed < 3.0), 0, np.round(speed * 10)).astype(int).flatten().tolist()
        d_flat = np.where(np.isnan(speed) | (speed < 3.0), 0, np.round(direction)).astype(int).flatten().tolist()
        arrow_data = {"s": s_flat, "d": d_flat}
    else:
        arrow_data = {"s": [], "d": []}

    with gzip.open(f"dist/data/arrows_{var_name}_m{m_idx}_s{step_idx}.json.gz", "wt", encoding="utf-8") as f:
        json.dump(arrow_data, f)

import gzip
import json
import numpy as np
from matplotlib.figure import Figure
import geojsoncontour
import config
import os
os.environ["MPLBACKEND"] = "Agg"

RENDER_ENV = None

def get_render_env():
    global RENDER_ENV
    if RENDER_ENV is None:
        fig = Figure()
        ax = fig.add_subplot(111)
        lon_1d = np.linspace(config.XMIN, config.XMAX, config.NX)
        lat_1d = np.linspace(config.YMIN, config.YMAX, config.NY)
        grid_lon, grid_lat = np.meshgrid(lon_1d, lat_1d)
        RENDER_ENV = (ax, grid_lon, grid_lat)
    return RENDER_ENV

def export_variable_step(var_name, m_idx, step_idx, data):
    ax, grid_lon, grid_lat = get_render_env()
    ax.clear()
    
    speed = data["speed"]
    
    if data.get("is_iqr", False):
        contourf = ax.contourf(
            grid_lon, grid_lat, speed,
            levels=config.IQR_LEVELS,
            colors=config.IQR_COLORS,
            alpha=0.55,
            corner_mask=True
        )
    else:
        contourf = ax.contourf(
            grid_lon, grid_lat, speed,
            levels=config.LEVELS,
            colors=config.COLORS,
            alpha=0.55,
            corner_mask=True
        )

    raw_geojson = geojsoncontour.contourf_to_geojson(contourf=contourf, ndigits=3)
    
    with gzip.open(f"dist/data/contours_{var_name}_m{m_idx}_s{step_idx}.json.gz", "wt", encoding="utf-8", compresslevel=3) as f:
        f.write(raw_geojson)

    # Pfeile NUR speichern wenn echte Pfeile existieren (Member 0 bis 10 für Wind/Wind1500)
    # Verhindert hunderte leere Dummy-Dateien bei Böen und Statistiken
    if data.get("has_arrows", False) and "dir" in data:
        direction = data["dir"]
        s_flat = np.where(np.isnan(speed) | (speed < 3.0), 0, np.round(speed * 10)).astype(int).flatten().tolist()
        d_flat = np.where(np.isnan(speed) | (speed < 3.0), 0, np.round(direction)).astype(int).flatten().tolist()
        arrow_data = {"s": s_flat, "d": d_flat}

        with gzip.open(f"dist/data/arrows_{var_name}_m{m_idx}_s{step_idx}.json.gz", "wt", encoding="utf-8", compresslevel=3) as f:
            json.dump(arrow_data, f)

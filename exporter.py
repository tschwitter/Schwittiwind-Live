import os
import gzip
import numpy as np
import config

def export_variable_step(model_name, run_id, var_name, m_idx, step_idx, data):
    speed = data["speed"]
    var_cfg = config.VARIABLES_CONFIG.get(var_name, {})
    palette = var_cfg.get("palette", "wind")

    # Alle Parameter einheitlich als uint8:
    # 255 = NaN (ungültig / unter Schwellenwert)
    # Sonne, Wolken, dBZ: 0 bis 100
    # Wind & Böen: 0 bis 250 km/h (ganzzahlig gerundet)
    max_val = 100 if palette in ["sun", "cloud", "dbz"] else 250

    s_arr = np.where(
        np.isnan(speed),
        255,
        np.clip(np.round(speed), 0, max_val)
    ).astype(np.uint8).ravel()

    payload_bytes = bytearray(s_arr.tobytes())

    # Windrichtung (nur wenn Windpfeile aktiv sind):
    # Als uint8 direkt angehängt (Winkel / 2 => 0..180, 255 = Windstille/NaN)
    if data.get("has_arrows", False) and "dir" in data:
        direction = data["dir"]
        d_arr = np.where(
            np.isnan(speed) | (speed < 2.5),
            255,
            np.round((direction % 360.0) / 2.0)
        ).astype(np.uint8).ravel()
        payload_bytes.extend(d_arr.tobytes())

    out_dir = f"dist/data/{model_name}/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    out_file = f"{out_dir}/grid_{var_name}_m{m_idx}_s{step_idx}.bin.gz"
    with gzip.open(out_file, "wb", compresslevel=3) as f:
        f.write(payload_bytes)

import os
import gzip
import numpy as np
import config

def export_variable_step(model_name, run_id, var_name, m_idx, step_idx, data):
    speed = data["speed"]
    var_cfg = config.VARIABLES_CONFIG.get(var_name, {})
    dtype_str = var_cfg.get("dtype", "int16")

    # 1. Hauptwerte (Speed, Wolken oder Sonne)
    if dtype_str == "uint8":
        # Wolken und Sonne: 0-100%, 255 = NaN (ungültig/unter Schwelle)
        s_arr = np.where(np.isnan(speed), 255, np.clip(np.round(speed), 0, 100)).astype(np.uint8).ravel()
    else:
        # Wind, Böen, dBZ: Skalierung * 10 in int16, -1 = NaN
        s_arr = np.where(np.isnan(speed), -1, np.round(speed * 10)).astype(np.int16).ravel()

    payload_bytes = bytearray(s_arr.tobytes())

    # 2. Windrichtung (nur wenn Windpfeile aktiv sind)
    # Wird als uint8 hinten angehängt (Winkel / 2 => 0..180, 255 = Windstille/NaN)
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

    # Binäres Schreiben als .bin.gz 
    out_file = f"{out_dir}/grid_{var_name}_m{m_idx}_s{step_idx}.bin.gz"
    with gzip.open(out_file, "wb", compresslevel=3) as f:
        f.write(payload_bytes)

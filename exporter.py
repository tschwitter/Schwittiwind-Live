import os
import gzip
import numpy as np

def export_variable_step(model_name, run_id, var_name, m_idx, step_idx, data):
    speed = data["speed"]

    # Volle 0.1-Präzision für ALLE Parameter: int16, skaliert * 10 (-1 = NaN)
    s_arr = np.where(np.isnan(speed), -1, np.round(speed * 10.0)).astype(np.int16).ravel()
    payload_bytes = bytearray(s_arr.tobytes())

    # Windrichtung nur anhängen, wenn Pfeile aktiv sind (niemals bei Statistiken!)
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

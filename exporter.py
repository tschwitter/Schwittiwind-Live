import os
import gzip
import numpy as np

def export_variable_step(model_name, run_id, var_name, m_idx, step_idx, data):
    """
    Exportiert ein Rasterfeld exakt im Byte-Shuffled Gzip-Format für app.js.
    Payload: [Low-Bytes int16] + [High-Bytes int16] + optional [uint8 directions]
    """
    speed = data["speed"]
    # 0.1 Skalierung für volle Präzision, NaN wird zu -1
    s_arr = np.where(np.isnan(speed), -1, np.round(speed * 10.0)).astype("<i2").ravel()

    # Byte-Shuffling
    raw_u8 = s_arr.view(np.uint8)
    payload = bytearray(raw_u8[0::2].tobytes())  # Low-Bytes
    payload.extend(raw_u8[1::2].tobytes())       # High-Bytes

    # Optionale Windrichtung bei Vektorfeldern
    if data.get("has_arrows", False) and "dir" in data:
        direction = data["dir"]
        d_arr = np.where(
            np.isnan(speed) | (speed < 2.5),
            255,
            np.round((direction % 360.0) / 2.0)
        ).astype(np.uint8).ravel()
        payload.extend(d_arr.tobytes())

    out_dir = f"dist/data/{model_name}/{run_id}"
    os.makedirs(out_dir, exist_ok=True)
    out_file = f"{out_dir}/grid_{var_name}_m{m_idx}_s{step_idx}.bin.gz"

    with gzip.open(out_file, "wb", compresslevel=3) as f:
        f.write(payload)

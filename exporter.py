import os
import gzip
import numpy as np

def export_variable_step(model_name, run_id, var_name, m_idx, step_idx, data):
    speed = data["speed"]
    # -1 für NaN, sonst mit 10 multiplizieren und als 16-Bit-Ganzzahl speichern (-32768 bis 32767)
    s_arr = np.where(np.isnan(speed), -1, np.round(speed * 10)).astype(np.int16).ravel()

    out_dir = f"dist/data/{model_name}/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    # Hebel 1: 24-Bit-Packung (16 Bit Speed + 8 Bit Direction = 3 Bytes pro Zelle)
    if data.get("has_arrows", False) and "dir" in data:
        direction = data["dir"]
        # Richtung (0..360°) wird durch 2 geteilt (0..180) -> passt in ein Byte (Uint8)
        d_u8 = np.where(np.isnan(speed) | (speed < 3.0), 0, np.round(direction / 2.0)).astype(np.uint8).ravel()
        raw_bytes = s_arr.tobytes() + d_u8.tobytes()
    else:
        raw_bytes = s_arr.tobytes()

    # Schnelle Kompression (wie zuvor Level 3) für maximale Pipeline-Geschwindigkeit
    with gzip.open(f"{out_dir}/grid_{var_name}_m{m_idx}_s{step_idx}.bin.gz", "wb", compresslevel=3) as f:
        f.write(raw_bytes)

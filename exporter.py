import os
import gzip
import numpy as np

def export_variable_step(model_name, run_id, var_name, m_idx, step_idx, data):
    speed = data["speed"]
    # -1 für NaN, sonst mit 10 multiplizieren und als 16-Bit-Ganzzahl speichern (-32768 bis 32767)
    s_arr = np.where(np.isnan(speed), -1, np.round(speed * 10)).astype(np.int16).ravel()

    out_dir = f"dist/data/{model_name}/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    # Wenn Richtungsdaten vorhanden sind, hängen wir sie lückenlos an
    if data.get("has_arrows", False) and "dir" in data:
        direction = data["dir"]
        d_arr = np.where(np.isnan(speed) | (speed < 3.0), 0, np.round(direction)).astype(np.int16).ravel()
        raw_bytes = np.concatenate([s_arr, d_arr]).tobytes()
    else:
        raw_bytes = s_arr.tobytes()

    # Reines Binär-Gzip (deutlich kleiner und schneller als JSON)
    with gzip.open(f"{out_dir}/grid_{var_name}_m{m_idx}_s{step_idx}.bin.gz", "wb", compresslevel=4) as f:
        f.write(raw_bytes)

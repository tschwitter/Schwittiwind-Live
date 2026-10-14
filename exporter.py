import os
import gzip
import numpy as np

def export_variable_step(model_name, run_id, var_name, m_idx, step_idx, data):
    speed = data["speed"]
    # -1 für NaN, ansonsten Multiplikation mit 10 und Rundung auf Int16 (-32768 bis 32767)
    s_arr = np.where(np.isnan(speed), -1, np.round(speed * 10)).astype(np.int16).ravel()

    out_dir = f"dist/data/{model_name}/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    # Wenn Windpfeile vorhanden sind, hängen wir das Richtungs-Array direkt an
    if data.get("has_arrows", False) and "dir" in data:
        direction = data["dir"]
        d_arr = np.where(np.isnan(speed) | (speed < 3.0), 0, np.round(direction)).astype(np.int16).ravel()
        # Beide Arrays lückenlos als zusammenhängender Byte-Block (s gefolgt von d)
        raw_bytes = np.concatenate([s_arr, d_arr]).tobytes()
    else:
        raw_bytes = s_arr.tobytes()

    # Mit Gzip komprimieren (bei reinen Binärdaten extrem effizient und schnell)
    with gzip.open(f"{out_dir}/grid_{var_name}_m{m_idx}_s{step_idx}.bin.gz", "wb", compresslevel=4) as f:
        f.write(raw_bytes)

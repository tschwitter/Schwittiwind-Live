import os
import gzip
import json
import numpy as np

def export_variable_step(model_name, var_name, m_idx, step_idx, data):
    speed = data["speed"]
    s_flat = np.where(np.isnan(speed), -1, np.round(speed * 10)).astype(int).flatten().tolist()

    if data.get("has_arrows", False) and "dir" in data:
        direction = data["dir"]
        d_flat = np.where(np.isnan(speed) | (speed < 3.0), 0, np.round(direction)).astype(int).flatten().tolist()
    else:
        d_flat = []

    payload = {"s": s_flat, "d": d_flat}

    out_dir = f"dist/data/{model_name}"
    os.makedirs(out_dir, exist_ok=True)

    with gzip.open(f"{out_dir}/grid_{var_name}_m{m_idx}_s{step_idx}.json.gz", "wt", encoding="utf-8", compresslevel=3) as f:
        json.dump(payload, f)

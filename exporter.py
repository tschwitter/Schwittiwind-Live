import gzip
import json
import numpy as np

def export_variable_step(var_name, m_idx, step_idx, data):
    speed = data["speed"]
    
    # NaN (z.B. Fels/Alpen) als -1 kodieren, Geschwindigkeiten auf 1 Dezimale (x10) runden
    s_flat = np.where(np.isnan(speed), -1, np.round(speed * 10)).astype(int).flatten().tolist()

    # Pfeilrichtungen nur beilegen wenn die Variable Pfeile unterstützt
    if data.get("has_arrows", False) and "dir" in data:
        direction = data["dir"]
        d_flat = np.where(np.isnan(speed) | (speed < 3.0), 0, np.round(direction)).astype(int).flatten().tolist()
    else:
        d_flat = []

    payload = {"s": s_flat, "d": d_flat}

    with gzip.open(f"dist/data/grid_{var_name}_m{m_idx}_s{step_idx}.json.gz", "wt", encoding="utf-8", compresslevel=3) as f:
        json.dump(payload, f)

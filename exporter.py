import os
import gzip
import orjson
import numpy as np

def export_variable_step(model_name, run_id, var_name, m_idx, step_idx, data):
    speed = data["speed"]
    # Direktes NumPy int32 Array ohne teures .tolist()
    s_flat = np.where(np.isnan(speed), -1, np.round(speed * 10)).astype(np.int32).ravel()

    if data.get("has_arrows", False) and "dir" in data:
        direction = data["dir"]
        d_flat = np.where(np.isnan(speed) | (speed < 3.0), 0, np.round(direction)).astype(np.int32).ravel()
    else:
        d_flat = []

    payload = {"s": s_flat, "d": d_flat}

    out_dir = f"dist/data/{model_name}/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    # orjson serialisiert NumPy-Arrays direkt in C/Rust (Option OPT_SERIALIZE_NUMPY)
    raw_bytes = orjson.dumps(payload, option=orjson.OPT_SERIALIZE_NUMPY)

    # Binäres Schreiben des JSON-Bytes-Streams in gzip
    with gzip.open(f"{out_dir}/grid_{var_name}_m{m_idx}_s{step_idx}.json.gz", "wb", compresslevel=3) as f:
        f.write(raw_bytes)

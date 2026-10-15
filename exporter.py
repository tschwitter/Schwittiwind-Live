import os
import gzip
import numpy as np

def export_variable_step(model_name, run_id, var_name, m_idx, step_idx, data):
    speed = data["speed"]

    # 1. Volle 0.1-Präzision für ALLE Parameter: int16 (Little-Endian '<i2'), -1 = NaN
    s_arr = np.where(np.isnan(speed), -1, np.round(speed * 10.0)).astype("<i2").ravel()

    # 2. BYTE-SHUFFLING: Trennung in Low-Bytes und High-Bytes
    raw_u8 = s_arr.view(np.uint8)
    low_bytes = raw_u8[0::2]   # Alle Low-Bytes (Feinabstufung)
    high_bytes = raw_u8[1::2]  # Alle High-Bytes (fast nur Nullen und 0xFF bei NaN)

    # 3. Payload zusammenstellen: [Alle Low-Bytes] + [Alle High-Bytes]
    payload_bytes = bytearray(low_bytes.tobytes())
    payload_bytes.extend(high_bytes.tobytes())

    # 4. Windrichtung (nur wenn Windpfeile aktiv sind, als uint8 hinten anhängen)
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

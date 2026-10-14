import os
import gzip
import numpy as np

def encode_deltas_2d(arr_2d):
    """
    Berechnet verlustfreie Zeilendifferenzen (Delta-Encoding) für 2D-Arrays.
    Erzeugt ein Array aus kleinen Zahlen um 0, das Gzip massiv komprimieren kann.
    """
    ny, nx = arr_2d.shape
    deltas = np.zeros_like(arr_2d, dtype=np.int16)
    
    # Erste Spalte jeder Zeile speichert den Absolutwert
    deltas[:, 0] = arr_2d[:, 0]
    # Alle folgenden Spalten speichern nur die Differenz zum linken Nachbarn
    deltas[:, 1:] = arr_2d[:, 1:] - arr_2d[:, :-1]
    
    return deltas.ravel()

def encode_angle_deltas_2d(dir_2d):
    """
    Berechnet kleinste Winkeldifferenzen für die Richtung (0..180 als Uint8).
    Behandelt den 360°-Rundlauf nahtlos.
    """
    ny, nx = dir_2d.shape
    deltas = np.zeros_like(dir_2d, dtype=np.int8)
    
    deltas[:, 0] = dir_2d[:, 0].astype(np.int8)
    diff = dir_2d[:, 1:].astype(np.int16) - dir_2d[:, :-1].astype(np.int16)
    
    # Kürzester Winkelweg über den 180er-Sprung (entspricht 360°)
    diff = (diff + 90) % 180 - 90
    deltas[:, 1:] = diff.astype(np.int8)
    
    return deltas.ravel()

def export_variable_step(model_name, run_id, var_name, m_idx, step_idx, data):
    speed = data["speed"]
    # -1 für NaN, sonst mit 10 multiplizieren
    s_raw = np.where(np.isnan(speed), -1, np.round(speed * 10)).astype(np.int16)
    
    # Delta-Encoding über die Gitterzeilen
    s_deltas = encode_deltas_2d(s_raw)
    
    out_dir = f"dist/data/{model_name}/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    if data.get("has_arrows", False) and "dir" in data:
        direction = data["dir"]
        # Richtung (0..360°) durch 2 teilen (0..180)
        d_raw = np.where(np.isnan(speed) | (speed < 3.0), 0, np.round(direction / 2.0)).astype(np.uint8)
        d_deltas = encode_angle_deltas_2d(d_raw)
        raw_bytes = s_deltas.tobytes() + d_deltas.tobytes()
    else:
        raw_bytes = s_deltas.tobytes()

    # Mit schneller Kompressionsstufe 3 komprimieren
    with gzip.open(f"{out_dir}/grid_{var_name}_m{m_idx}_s{step_idx}.bin.gz", "wb", compresslevel=3) as f:
        f.write(raw_bytes)

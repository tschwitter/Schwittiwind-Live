import os
import numpy as np
from PIL import Image
import config

def export_variable_step(model_name, run_id, var_name, m_idx, step_idx, data):
    speed = data["speed"]
    ny, nx = config.NY, config.NX  # 240, 400

    # 1. Geschwindigkeit aufbereiten: Skalierung * 10
    # NaN/ungültig als 65535 markieren
    valid_mask = ~np.isnan(speed)
    speed_scaled = np.where(valid_mask, np.clip(np.round(speed * 10), 0, 65534), 65535).astype(np.uint16)

    # 16-Bit-Geschwindigkeit in zwei 8-Bit-Farbkanäle aufteilen (R = High-Byte, G = Low-Byte)
    r_chan = (speed_scaled >> 8).astype(np.uint8)
    g_chan = (speed_scaled & 0xFF).astype(np.uint8)

    # 2. Windrichtung aufbereiten (Kanal B)
    if data.get("has_arrows", False) and "dir" in data:
        direction = data["dir"]
        # Richtung (0..360°) durch 2 teilen (0..180) -> passt in 8-Bit
        b_chan = np.where(valid_mask & (speed >= 3.0), np.round(direction / 2.0), 0).astype(np.uint8)
    else:
        b_chan = np.zeros((ny, nx), dtype=np.uint8)

    # 3. 3-Kanal-RGB-Bild (240x400x3) zusammensetzen
    rgb_arr = np.stack([r_chan, g_chan, b_chan], axis=-1)

    out_dir = f"dist/data/{model_name}/{run_id}"
    os.makedirs(out_dir, exist_ok=True)

    out_path = f"{out_dir}/grid_{var_name}_m{m_idx}_s{step_idx}.png"

    # Als optimiertes PNG speichern (Hardware-optimierte 2D-Kompression)
    img = Image.fromarray(rgb_arr, mode="RGB")
    img.save(out_path, format="PNG", optimize=True)

from datetime import timedelta
from meteodatalab import ogd_api
import numpy as np
import config

def fetch_weather_data():
    print("1. Kontaktiere MeteoSchweiz für den neuesten ICON-CH1 Hauptlauf (Wind & Böen)...")
    lead_times = [timedelta(hours=h) for h in range(config.ANZAHL_STUNDEN + 1)]

    # Hauptlauf (Control): U_10M, V_10M und VMAX_10M
    req_u_h = ogd_api.Request(collection="ogd-forecasting-icon-ch1", variable="U_10M", ref_time="latest", perturbed=False, lead_time=lead_times)
    req_v_h = ogd_api.Request(collection="ogd-forecasting-icon-ch1", variable="V_10M", ref_time="latest", perturbed=False, lead_time=lead_times)
    req_g_h = ogd_api.Request(collection="ogd-forecasting-icon-ch1", variable="VMAX_10M", ref_time="latest", perturbed=False, lead_time=lead_times)
    
    ds_u_h = ogd_api.get_from_ogd(req_u_h)
    ds_v_h = ogd_api.get_from_ogd(req_v_h)
    ds_g_h = ogd_api.get_from_ogd(req_g_h)

    ref_time_raw = ds_u_h.coords['ref_time'].values[0]
    ref_time_str = str(ref_time_raw).split('.')[0] + "Z"
    print(f"-> Referenzzeitpunkt (Modellstart): {ref_time_str}")

    # Ensembles (Perturbed)
    print("2. Lade Ensemble-Mitglieder herunter (Wind & Böen)...")
    req_u_e = ogd_api.Request(collection="ogd-forecasting-icon-ch1", variable="U_10M", ref_time=ref_time_str, perturbed=True, lead_time=lead_times)
    req_v_e = ogd_api.Request(collection="ogd-forecasting-icon-ch1", variable="V_10M", ref_time=ref_time_str, perturbed=True, lead_time=lead_times)
    req_g_e = ogd_api.Request(collection="ogd-forecasting-icon-ch1", variable="VMAX_10M", ref_time=ref_time_str, perturbed=True, lead_time=lead_times)
    
    ds_u_e = ogd_api.get_from_ogd(req_u_e)
    ds_v_e = ogd_api.get_from_ogd(req_v_e)
    ds_g_e = ogd_api.get_from_ogd(req_g_e)

    # Bereinigung & Zuschnitt auf die Schweiz
    print("3. Filtere Gitterzellen auf die Schweiz...")
    u_h = ds_u_h.squeeze()
    v_h = ds_v_h.squeeze()
    g_h = ds_g_h.squeeze()
    u_e = ds_u_e.squeeze()
    v_e = ds_v_e.squeeze()
    g_e = ds_g_e.squeeze()

    lats = u_h.coords['lat'].values
    lons = u_h.coords['lon'].values
    valid_cells = np.where((lats >= config.LAT_MIN) & (lats <= config.LAT_MAX) & (lons >= config.LON_MIN) & (lons <= config.LON_MAX))[0]

    return (
        u_h.isel(cell=valid_cells), v_h.isel(cell=valid_cells), g_h.isel(cell=valid_cells),
        u_e.isel(cell=valid_cells), v_e.isel(cell=valid_cells), g_e.isel(cell=valid_cells),
        ref_time_raw
    )

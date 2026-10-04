# ================= CONFIGURATION =================
ANZAHL_STUNDEN = 33

# 1km-Originalauflösung der Schweiz
NX, NY = 400, 240

# Bounding Box Schweiz (+ Puffer)
XMIN, XMAX = 5.8, 10.7
YMIN, YMAX = 45.6, 47.9

# Geografischer Vorfilter
LAT_MIN, LAT_MAX = 45.5, 48.0
LON_MIN, LON_MAX = 5.7, 10.8

# Modulare Variablen-Konfiguration
VARIABLES_CONFIG = {
    "wind":     {"label": "10m Wind",     "type": "surface",  "has_ensemble": True,  "has_arrows": True,  "palette": "wind"},
    "gust":     {"label": "Böen",         "type": "surface",  "has_ensemble": True,  "has_arrows": False, "palette": "wind"},
    "dbz":      {"label": "Radar (dBZ)",  "type": "surface",  "has_ensemble": False,  "has_arrows": False, "palette": "dbz"},
    "sun":      {"label": "Sonne %",      "type": "surface",  "has_ensemble": False,  "has_arrows": False, "palette": "sun"},
    "wind1000": {"label": "1000m Wind",   "type": "altitude", "altitude": 1000.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
    "wind1500": {"label": "1500m Wind",   "type": "altitude", "altitude": 1500.0, "has_ensemble": True,  "has_arrows": True, "palette": "wind"},
    "wind2000": {"label": "2000m Wind",   "type": "altitude", "altitude": 2000.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
    "wind2500": {"label": "2500m Wind",   "type": "altitude", "altitude": 2500.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
    "wind3000": {"label": "3000m Wind",   "type": "altitude", "altitude": 3000.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
    "wind3500": {"label": "3500m Wind",   "type": "altitude", "altitude": 3500.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
}

VARIABLES = list(VARIABLES_CONFIG.keys())

# Standard-Farbskala für Wind & Böen (0 bis 45+ km/h)
LEVELS = [0, 4, 7, 11, 14, 18, 23, 27, 36, 45, 120]
COLORS = [
    '#f1f6ff', '#baddf3', '#5cd184', '#89db4c', '#fed148',
    '#fca643', '#eb4d3c', '#9c285e', '#7a0fd1', '#2d21a9'
]

# Feine Farbskala für die Unsicherheit / Interquantilabstand
IQR_LEVELS = [0, 2, 4, 6, 8, 10, 12, 15, 20, 30, 120]
IQR_COLORS = [
    '#ffffff00', '#e0f3db', '#a8ddb5', '#7bccc4', '#4eb3d3',
    '#2b8cbe', '#fec44f', '#fe9929', '#ec7014', '#d7301f'
]

# ================= NEU: Sonnenscheindauer (%) =================
SUN_LEVELS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
SUN_COLORS = [
    '#ffffff00',  # 0-10%: transparent
    '#fff69c',    # 10-20%
    '#fee578',    # 20-30%
    '#fcd159',    # 30-40%
    '#fbb847',    # 40-50%
    '#f99d33',    # 50-60%
    '#f17c24',    # 60-70%
    '#e65c1e',    # 70-80%
    '#d9491b',    # 80-90%
    '#932512'     # 90-100%
]

# ================= NEU: Radar-Reflektivität (dBZ) =================
# Exakte Zwischenabstufungen laut Kachelmann/Meteologix Radar-Skala
DBZ_LEVELS = [
    7.0, 13.0, 19.0, 24.0, 28.0, 31.0, 36.0, 41.0, 43.0, 45.0,
    47.0, 49.0, 51.0, 52.0, 53.0, 54.0, 54.5, 55.0, 56.0, 56.5,
    57.0, 58.0, 58.5, 59.0, 59.5, 60.0, 60.5, 61.0, 64.0, 100.0
]

DBZ_COLORS = [
    '#6f7a88',  # 7-13
    '#54637b',  # 13-19
    '#385299',  # 19-24
    '#1f59fa',  # 24-28
    '#009121',  # 28-31
    '#00bf1b',  # 31-36
    '#d7f32f',  # 36-41
    '#fff300',  # 41-43
    '#ffcc00',  # 43-45
    '#ffa000',  # 45-47
    '#ff7400',  # 47-49
    '#ff4500',  # 49-51
    '#ff1d00',  # 51-52
    '#eb0000',  # 52-53
    '#c80000',  # 53-54
    '#5a0026',  # 54-54.5
    '#460052',  # 54.5-55
    '#68007e',  # 55-56
    '#8a00a4',  # 56-56.5
    '#b000c2',  # 56.5-57
    '#d200e0',  # 57-58
    '#f200f2',  # 58-58.5
    '#f425e7',  # 58.5-59
    '#f64edb',  # 59-59.5
    '#f872d6',  # 59.5-60
    '#fa96d5',  # 60-60.5
    '#fcb4db',  # 60.5-61
    '#fdd4eb',  # 61-64
    '#feeef6'   # >64
]

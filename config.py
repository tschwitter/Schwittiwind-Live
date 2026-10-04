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
    "dbz":      {"label": "Radar (dBZ)",  "type": "surface",  "has_ensemble": False, "has_arrows": False, "palette": "dbz"},
    "sun":      {"label": "Sonne %",      "type": "surface",  "has_ensemble": False, "has_arrows": False, "palette": "sun"},
    "wind1000": {"label": "1000m Wind",   "type": "altitude", "altitude": 1000.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
    "wind1500": {"label": "1500m Wind",   "type": "altitude", "altitude": 1500.0, "has_ensemble": True,  "has_arrows": True, "palette": "wind"},
    "wind2000": {"label": "2000m Wind",   "type": "altitude", "altitude": 2000.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
    "wind2500": {"label": "2500m Wind",   "type": "altitude", "altitude": 2500.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
    "wind3000": {"label": "3000m Wind",   "type": "altitude", "altitude": 3000.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
    "wind3500": {"label": "3500m Wind",   "type": "altitude", "altitude": 3500.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
}

# ================= SCHNELLAUSWAHL FÜR TESTS =================
# Setze oder entferne das '#' vor Variablen, um sie blitzschnell ein- oder auszuschalten!
ACTIVE_VARIABLES = [
     "wind",
    # "gust",
    "dbz",
    "sun",
    # "wind1000",
    # "wind1500",
    # "wind2000",
    # "wind2500",
    # "wind3000",
    # "wind3500",
]

VARIABLES = [v for v in ACTIVE_VARIABLES if v in VARIABLES_CONFIG]

# Standard-Farbskala für Wind & Böen
LEVELS = [0, 4, 7, 11, 14, 18, 23, 27, 36, 45, 120]
COLORS = [
    '#f1f6ff', '#baddf3', '#5cd184', '#89db4c', '#fed148',
    '#fca643', '#eb4d3c', '#9c285e', '#7a0fd1', '#2d21a9'
]

IQR_LEVELS = [0, 2, 4, 6, 8, 10, 12, 15, 20, 30, 120]
IQR_COLORS = [
    '#ffffff00', '#e0f3db', '#a8ddb5', '#7bccc4', '#4eb3d3',
    '#2b8cbe', '#fec44f', '#fe9929', '#ec7014', '#d7301f'
]

# Sonnenschein-Farbskala (0 bis 100 %)
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

# Radar-Reflektivität (dBZ) – Exakt 20 Stufen laut Kachelmann/Meteologix
DBZ_LEVELS = [
    7.0, 19.0, 24.0, 31.0, 41.0, 45.0, 47.0, 49.0, 51.0, 52.0,
    53.0, 54.0, 55.0, 56.0, 57.0, 58.0, 59.0, 60.0, 61.0, 64.0, 100.0
]

DBZ_COLORS = [
    '#687687',  # 7-19:  Dunkles Blaugrau / Schiefer
    '#395b87',  # 19-24: Stahlblau
    '#1a57f5',  # 24-31: Kräftiges Blau
    '#00a600',  # 31-41: Reines Grün
    '#ffee00',  # 41-45: Gelb
    '#ffb300',  # 45-47: Bernstein / Gelborange
    '#ff7800',  # 47-49: Orange
    '#ff4000',  # 49-51: Dunkelorange
    '#ff1400',  # 51-52: Rotorange
    '#d80000',  # 52-53: Helles Rot
    '#ad0000',  # 53-54: Dunkelrot
    '#580036',  # 54-55: Tiefes Weinrot / Aubergine
    '#440064',  # 55-56: Dunkelviolett
    '#6c0096',  # 56-57: Violett
    '#9200b8',  # 57-58: Lila / Purpur
    '#bc00ce',  # 58-59: Helles Purpur / Magenta
    '#e200da',  # 59-60: Magenta
    '#f432cb',  # 60-61: Kräftiges Pink
    '#fa7fd6',  # 61-64: Rosa
    '#ffd4f6'   # >64:   Sehr helles Zartrosa / Fast Weiß
]

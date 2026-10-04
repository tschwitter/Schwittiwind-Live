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
    "dbz":      {"label": "Radar (dBZ)",  "type": "surface",  "has_ensemble": True,  "has_arrows": False, "palette": "dbz"},
    "sun":      {"label": "Sonne %",      "type": "surface",  "has_ensemble": True,  "has_arrows": False, "palette": "sun"},
    
    # NEU: Die 4 Wolkenstockwerke
    "clct":     {"label": "Wolken",       "type": "surface",  "has_ensemble": True,  "has_arrows": False, "palette": "cloud"},
    "clch":     {"label": "Hohe Wolken",  "type": "surface",  "has_ensemble": False, "has_arrows": False, "palette": "cloud"},
    "clcm":     {"label": "Mittl. Wolken","type": "surface",  "has_ensemble": False, "has_arrows": False, "palette": "cloud"},
    "clcl":     {"label": "Tiefe Wolken", "type": "surface",  "has_ensemble": False, "has_arrows": False, "palette": "cloud"},

    # Höhenwinde
    "wind1000": {"label": "1000m Wind",   "type": "altitude", "altitude": 1000.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
    "wind1500": {"label": "1500m Wind",   "type": "altitude", "altitude": 1500.0, "has_ensemble": True,  "has_arrows": True, "palette": "wind"},
    "wind2000": {"label": "2000m Wind",   "type": "altitude", "altitude": 2000.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
    "wind2500": {"label": "2500m Wind",   "type": "altitude", "altitude": 2500.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
    "wind3000": {"label": "3000m Wind",   "type": "altitude", "altitude": 3000.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
    "wind3500": {"label": "3500m Wind",   "type": "altitude", "altitude": 3500.0, "has_ensemble": False, "has_arrows": True, "palette": "wind"},
}

# Schnellauswahl für Tests (einfach '#' setzen oder entfernen)
ACTIVE_VARIABLES = [
    "wind",
    "gust",
    "dbz",
    "sun",
    "clct",
    "clch",
    "clcm",
    "clcl",
    "wind1000",
    "wind1500",
    "wind2000",
    "wind2500",
    "wind3000",
    "wind3500",
]

VARIABLES = [v for v in ACTIVE_VARIABLES if v in VARIABLES_CONFIG]

# ================= HAUPT-FARBSKALEN =================
LEVELS = [0, 4, 7, 11, 14, 18, 23, 27, 36, 45, 120]
COLORS = [
    '#f1f6ff', '#baddf3', '#5cd184', '#89db4c', '#fed148',
    '#fca643', '#eb4d3c', '#9c285e', '#7a0fd1', '#2d21a9'
]

SUN_LEVELS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
SUN_COLORS = [
    '#ffffff00', '#fff69c', '#fee578', '#fcd159', '#fbb847',
    '#f99d33', '#f17c24', '#e65c1e', '#d9491b', '#932512'
]

DBZ_LEVELS = [
    7.0, 19.0, 24.0, 31.0, 41.0, 45.0, 47.0, 49.0, 51.0, 52.0,
    53.0, 54.0, 55.0, 56.0, 57.0, 58.0, 59.0, 60.0, 61.0, 64.0, 100.0
]
DBZ_COLORS = [
    '#687687', '#395b87', '#1a57f5', '#00a600', '#ffee00',
    '#ffb300', '#ff7800', '#ff4000', '#ff1400', '#d80000',
    '#ad0000', '#580036', '#440064', '#6c0096', '#9200b8',
    '#bc00ce', '#e200da', '#f432cb', '#fa7fd6', '#ffd4f6'
]

# ================= NEU: WOLKEN-FARBSKALA (mit 10% Stufe) =================
# Exakte Graustufen laut Screenshot (10 Intervalle von 10% bis 100%)
CLOUD_LEVELS = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 95.0, 100.0]
CLOUD_COLORS = [
    '#f0f2f5',  # 10-20%: Hauchdünner Schleier
    '#dfe3e8',  # 20-30%
    '#cbcfd6',  # 30-40%
    '#b4b9c2',  # 40-50%
    '#9ba1ac',  # 50-60%
    '#828894',  # 60-70%
    '#686e7a',  # 70-80%
    '#505561',  # 80-90%
    '#3a3e48',  # 90-95%
    '#23262c'   # 95-100%: Dichte Bewölkung / Dunkelgrau
]

# ================= SPEZIFISCHE IQR-SKALEN =================
IQR_BASE_COLORS = [
    '#ffffff00', '#e0f3db', '#a8ddb5', '#7bccc4', '#4eb3d3',
    '#2b8cbe', '#fec44f', '#fe9929', '#ec7014', '#d7301f'
]

IQR_WIND_LEVELS = [0, 2, 4, 6, 8, 10, 14, 18, 24, 30, 120]
IQR_WIND_COLORS = IQR_BASE_COLORS

IQR_DBZ_LEVELS = [0, 6, 12, 18, 25, 32, 40, 48, 56, 65, 120]
IQR_DBZ_COLORS = IQR_BASE_COLORS

IQR_SUN_LEVELS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
IQR_SUN_COLORS = IQR_BASE_COLORS

IQR_CLOUD_LEVELS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
IQR_CLOUD_COLORS = IQR_BASE_COLORS

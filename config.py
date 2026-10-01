# ================= CONFIGURATION =================
# Prognose-Horizont in Stunden
ANZAHL_STUNDEN = 33

# 1km-Originalauflösung der Schweiz
NX, NY = 400, 240

# Bounding Box Schweiz (+ Puffer)
XMIN, XMAX = 5.8, 10.7
YMIN, YMAX = 45.6, 47.9

# Geografischer Vorfilter
LAT_MIN, LAT_MAX = 45.5, 48.0
LON_MIN, LON_MAX = 5.7, 10.8

# Verfügbare Variablen (NEU: wind1500)
VARIABLES = ["wind", "gust", "wind1500"]
TARGET_ALTITUDE = 1500.0  # Meter über Meer

# Standard-Farbskala für Wind & Böen (0 bis 45+ km/h)
LEVELS = [0, 4, 7, 11, 14, 18, 23, 27, 36, 45, 120]
COLORS = [
    '#f1f6ff', '#baddf3', '#5cd184', '#89db4c', '#fed148',
    '#fca643', '#eb4d3c', '#9c285e', '#7a0fd1', '#2d21a9'
]

# Feine Farbskala für die Unsicherheit / Interquantilabstand (0 bis 30 km/h)
IQR_LEVELS = [0, 2, 4, 6, 8, 10, 12, 15, 20, 30, 120]
IQR_COLORS = [
    '#ffffff00', '#e0f3db', '#a8ddb5', '#7bccc4', '#4eb3d3',
    '#2b8cbe', '#fec44f', '#fe9929', '#ec7014', '#d7301f'
]

# ================= CONFIGURATION =================
NX, NY = 400, 240

XMIN, XMAX = 5.8, 10.7
YMIN, YMAX = 45.6, 47.9

LAT_MIN, LAT_MAX = 45.5, 48.0
LON_MIN, LON_MAX = 5.7, 10.8

VARIABLES_CONFIG = {
    "wind":     {"label": "10m Wind",     "type": "surface",  "has_arrows": True,  "palette": "wind"},
    "gust":     {"label": "Böen",         "type": "surface",  "has_arrows": False, "palette": "wind"},
    "dbz":      {"label": "Radar (dBZ)",  "type": "surface",  "has_arrows": False, "palette": "dbz"},
    "sun":      {"label": "Sonne %",      "type": "surface",  "has_arrows": False, "palette": "sun"},
    "clct":     {"label": "Wolken",       "type": "surface",  "has_arrows": False, "palette": "cloud"},
    "clch":     {"label": "Hohe Wolken",  "type": "surface",  "has_arrows": False, "palette": "cloud"},
    "clcm":     {"label": "Mittl. Wolken","type": "surface",  "has_arrows": False, "palette": "cloud"},
    "clcl":     {"label": "Tiefe Wolken", "type": "surface",  "has_arrows": False, "palette": "cloud"},
    "wind1000": {"label": "1000m Wind",   "type": "altitude", "altitude": 1000.0, "has_arrows": True,  "palette": "wind"},
    "wind1500": {"label": "1500m Wind",   "type": "altitude", "altitude": 1500.0, "has_arrows": True,  "palette": "wind"},
    "wind2000": {"label": "2000m Wind",   "type": "altitude", "altitude": 2000.0, "has_arrows": True,  "palette": "wind"},
    "wind2500": {"label": "2500m Wind",   "type": "altitude", "altitude": 2500.0, "has_arrows": True,  "palette": "wind"},
    "wind3000": {"label": "3000m Wind",   "type": "altitude", "altitude": 3000.0, "has_arrows": True,  "palette": "wind"},
    "wind3500": {"label": "3500m Wind",   "type": "altitude", "altitude": 3500.0, "has_arrows": True,  "palette": "wind"},
}

VARIABLES = list(VARIABLES_CONFIG.keys())

# ================= MODELL-STEUERUNG (VOLLE 24H HISTORIE) =================
MODELS_CONFIG = {
    "icon-ch1": {
        "name": "ICON-CH1 (1km)",
        "collection": "ogd-forecasting-icon-ch1",
        "hhl_asset": "vertical_constants_icon-ch1-eps.grib2",
        "hours": 33,
        "max_members": 11,
        "max_runs": 8,  # Volle 24 Stunden (8 Läufe à 3 Stunden)
        "active_variables": ["wind"],
        #, "gust", "dbz", "sun", "clct", "clch", "clcm", "clcl", "wind1000", "wind1500", "wind2000", "wind2500", "wind3000", "wind3500"
        "ensemble_variables": [],
        #"wind", "gust", "dbz", "sun", "clct", "clch", "clcm", "clcl",  "wind1500"
        "max_chunks": 4
    },
    "icon-ch2": {
        "name": "ICON-CH2 (2.1km)",
        "collection": "ogd-forecasting-icon-ch2",
        "hhl_asset": "vertical_constants_icon-ch2-eps.grib2",
        "hours": 120,
        "max_members": 21,
        "max_runs": 4,  # Volle 24 Stunden (4 Läufe à 6 Stunden)
        "active_variables": ["wind"],
        #, "gust", "dbz", "sun", "clct", "clch", "clcm", "clcl"
        "ensemble_variables": [],
        #"wind"
        "max_chunks": 4
    }
}

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

CLOUD_LEVELS = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 95.0, 100.0]
CLOUD_COLORS = [
    '#f0f2f5', '#dfe3e8', '#cbcfd6', '#b4b9c2', '#9ba1ac',
    '#828894', '#686e7a', '#505561', '#3a3e48', '#23262c'
]

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

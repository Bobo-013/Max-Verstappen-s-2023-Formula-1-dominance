# 1. Beállítások
# Színek és betűtípus
RED = "#E10600"
BG = "#15151E"
PANEL = "#1F1F2B"
TEXT = "#F2F2F2"
MUTED = "#9A9AAA"
FONT = "'Titillium Web', 'Segoe UI', Arial, sans-serif"

SERIES_COLORS = [RED, TEXT, MUTED, "#3671C6"]
 
# Földgömb forgatása
START_LON = 20      # kezdő hosszúsági fok
START_LAT = 25      # dőlésszög
STEP_DEG = 0.5      # ennyi fokot fordul egy tick alatt
INTERVAL_MS = 50    # tick gyakorisága (ms)
 
# Oldalváltás animációi (másodperc)
PAGE_OUT_S = 0.7    
PAGE_IN_S = 0.9     
 
# Dobogó animációja.
PODIUM_DELAY = {3: 0.0, 2: 0.9, 1: 1.8}

# Zene
THEME_FILE = "/assets/music/f1_theme.mp3"
THEME_VOL = 0.25       # háttérzene hangereje
ANTHEM_VOL = 0.6       # himnusz hangereje
ANTHEM_S = 20           # ennyi másodpercig szól a himnusz (az utolsó 1 mp halkul)
ANTHEM_DELAY = 0.0     # ennyi másodperc késéssel indul a himnusz a dobogó megjelenése után

SUMMARY_SONG_FILE = "assets/music/summary_theme.mp3"
SUMMARY_VOL = 0.25


# Győztes pilóta -> himnusz fájlneve
WINNER_ANTHEM = {"VER": "nl", "PER": "mx", "SAI": "es", "LEC": "mc", "HAM": "gb", "PIA": "au"}
TEAM_ANTHEM = {"Red Bull Racing": "at", "Ferrari": "it", "Mercedes": "de", "McLaren": "gb"}
# Pontállás-sávok (futamoldal): egy sor magassága (px), és hány másodperc késleltetés
LAP_ROW_H = 34
LAP_DELAY = 2.4

# Stratégia
LAPS_FILES = {"R": "Laps.csv", "S": "Sprint_Laps.csv"}
TYRE_COLORS = {"SOFT": "#E10600", "MEDIUM": "#FFC72C", "HARD": "#FFFFFF",
               "INTERMEDIATE": "#00B140", "WET": "#0090FF", "UNKNOWN": "#6B6B7B"}
TYRE_NAMES = {"SOFT": "Soft", "MEDIUM": "Medium", "HARD": "Hard",
              "INTERMEDIATE": "Intermediate", "WET": "Wet", "UNKNOWN": "Ismeretlen"}

PIT_MAX_S = 60 # Ennél hosszabb kiállást valószínűleg piros zászló okozta

# Megszakítások
TRACK_STATUS = {"RED":    ("Piros zászló", "#E10600", 0.45),
               "SC":     ("Safety car", "#FF9F1C", 0.30),
               "VSC":    ("Virtual SC", "#B388FF", 0.25),
               "YELLOW": ("Sárga zászló", "#FFEB3B", 0.28)}

# Időjárás ikonok
NIGHT_LABEL = "Éjszakai"
NIGHT_RACES = ("Bahrain", "Saudi Arabian", "Singapore", "Qatar", "Las Vegas", "Abu Dhabi")
WX_ICON = {"Napos": "sunny", "Részben felhős": "partly_cloudy", "Felhős": "cloudy",
           "Esős": "rainy", NIGHT_LABEL: "night"}
 
# Közös stílusok
card = {"background": PANEL, "padding": "20px", "borderRadius": "8px"}
header_row = {"display": "flex", "justifyContent": "space-between", "alignItems": "center"}
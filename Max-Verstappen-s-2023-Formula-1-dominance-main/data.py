from pathlib import Path

import pandas as pd

from config import LAPS_FILES, NIGHT_LABEL, NIGHT_RACES, TYRE_NAMES, WX_ICON


# 2. Adatok betöltése
BASE = Path(__file__).resolve().parent
P = BASE / "data" / "processed"

# Keverékek elérési útja
TYRE_IMG_DIR = BASE / "assets" / "images" / "tires"
TYRE_IMGS = {}
if TYRE_IMG_DIR.exists():
    _files = {f.stem.lower(): f.name for f in TYRE_IMG_DIR.glob("*.png")}
    for _k, _n in TYRE_NAMES.items():
        if _n.lower() in _files:
            TYRE_IMGS[_k] = f"/assets/images/tires/{_files[_n.lower()]}"
for _k, _n in TYRE_NAMES.items():
    if _k not in TYRE_IMGS:
        print("Gumi kép hiányzik:", f"assets/images/{_n}.png")

for f in ["race_results.csv", "sprint_results.csv", "quali_results.csv",
          "sprint_summary.csv", "sprint_best_laps.csv"]:
    p = P / f
    print(f, "->", f"{len(pd.read_csv(p))} sor" if p.exists() else "NINCS MEG")

for f in ["Results.csv", "Sprint_Results.csv"]:
    p = BASE / "data" / f
    if not p.exists():
        print("\n", f, "-> NINCS MEG itt:", p)
        continue
    d = pd.read_csv(p, usecols=lambda c: c in {"Race Type", "Q1", "Q2", "Q3", "RoundNumber"})
    print("\n", f)
    if "Race Type" in d.columns:
        print(d["Race Type"].value_counts(dropna=False).to_string())
    for c in ("Q1", "Q2", "Q3"):
        if c in d.columns:
            print(c, "kitöltött sorok:", int(d[c].notna().sum()))

            
drivers = pd.read_csv(P / "drivers.csv", dtype={"TeamColor": str})
teams = pd.read_csv(P / "teams.csv", dtype={"TeamColor": str})
d_cum = pd.read_csv(P / "driver_cumulative_points.csv", index_col=0)
t_cum = pd.read_csv(P / "team_cumulative_points.csv", index_col=0)
events = pd.read_csv(P / "events.csv")
stats = pd.read_csv(P / "verstappen_stats.csv", index_col=0)["value"].astype(int)

#Oldalsáv labels
LABELS = {
    "races": "Futamok",
    "wins": "Győzelmek",
    "podiums": "Dobogós helyezések",
    "poles": "Pole pozíciók",
    "fastest_laps": "Leggyorsabb körök",
    "laps_completed": "Teljesített körök",
    "points": "Pontok",
}

# Futamszám -> futam neve
round_names = events.set_index("RoundNumber")["EventName"].to_dict()
 
# Futamonkénti eredmények
results = pd.read_csv(
    BASE / "data" / "Results.csv",
    usecols=["Abbreviation", "FullName", "TeamName", "TeamColor",
             "Position", "GridPosition", "Points", "RoundNumber"],
    dtype={"TeamColor": str},
)
 
# Rövidítés
NAMES = results.drop_duplicates("Abbreviation").set_index("Abbreviation")["FullName"].to_dict()
 
# Melyik pilóta melyik körének telemetriája van meg
_ti = P / "telemetry_index.csv"
tel_index = (pd.read_csv(_ti).dropna(subset=["LapTime"]) if _ti.exists()
             else pd.DataFrame(columns=["RoundNumber", "Driver", "LapTime", "LapNumber"]))
 
# Futam összefoglaló (időjárás, átlagos köridők)
_sf = P / "race_summary.csv"
summary = pd.read_csv(_sf).set_index("RoundNumber") if _sf.exists() else pd.DataFrame()

# Session választó
_EMPTY_TI = pd.DataFrame(columns=["RoundNumber", "Driver", "LapTime", "LapNumber"])

SESS = {"R": dict(label="Futam", noun="futam", plural="futamok", slug="race",
                  art="a futam", back="← Vissza a futamhoz",
                  results=results, summary=summary, tel_index=tel_index, tel_dir="telemetry")}

def _opt_csv(name, **kw):
    p = P / name
    return pd.read_csv(p, **kw) if p.exists() else None

_sp = _opt_csv("sprint_results.csv", dtype={"TeamColor": str})
if _sp is not None and not _sp.empty:
    _ss, _bl = _opt_csv("sprint_summary.csv"), _opt_csv("sprint_best_laps.csv")
    SESS["S"] = dict(label="Sprint", noun="sprint", plural="sprintek", slug="sprint",
                     art="a sprint", back="← Vissza a sprinthez", results=_sp,
                     summary=_ss.set_index("RoundNumber") if _ss is not None else pd.DataFrame(),
                     tel_index=_bl.dropna(subset=["LapTime"]) if _bl is not None else _EMPTY_TI,
                     tel_dir="")

_q = _opt_csv("quali_results.csv", dtype={"TeamColor": str})
if _q is not None and not _q.empty:
    SESS["Q"] = dict(label="Időmérő", noun="időmérő", plural="időmérők", slug="quali",
                     art="az időmérő", back="← Vissza az időméréshez", results=_q,
                     summary=pd.DataFrame(), tel_index=_EMPTY_TI, tel_dir="")

for _cfg in SESS.values():   # melyik fordulóban van az adott session
    _cfg["rounds"] = sorted(int(r) for r in _cfg["results"]["RoundNumber"].dropna().unique())
    for _a, _n in (_cfg["results"].drop_duplicates("Abbreviation")
                   .set_index("Abbreviation")["FullName"].items()):
        NAMES.setdefault(_a, _n)

# Az ikon fájl elérési útja
def _wx_path(code) -> str:
    if code and (BASE / "assets" / "images" / "weather" / f"{code}.svg").exists():
        return f"/assets/images/weather/{code}.svg"
    return ""

# Az ikon egy időjárás-értékhez
def wx_icon(condition) -> str:
    return _wx_path(WX_ICON.get(condition))

for _c, _code in WX_ICON.items():
    if not _wx_path(_code):
        print("Időjárás ikon hiányzik:", f"assets/weather/{_code}.svg")

# Az éjszakai futamok külön csoportot kapnak
def _apply_night(sm):
    if sm is None or sm.empty or "condition" not in sm.columns:
        return sm
    sm = sm.copy()
    for rn in sm.index:
        name = round_names.get(int(rn), "").lower()
        if any(k.lower() in name for k in NIGHT_RACES):
            sm.loc[rn, "condition"] = NIGHT_LABEL
    return sm

for _cfg in SESS.values():
    _cfg["summary"] = _apply_night(_cfg["summary"])

SLUG2KEY = {c["slug"]: k for k, c in SESS.items()}

# Egy session oldalának címe
def sess_url(rn, s="R"):
    return f"/race/{rn}" if s == "R" else f"/race/{rn}/{SESS[s]['slug']}"

# Az útvonalból a session
def session_from_path(path):
    try:
        p = path.strip("/").split("/")
        slug = p[2] if p[0] == "race" else p[3]
        return SLUG2KEY.get(slug, "R")
    except (AttributeError, IndexError):
        return "R"

# Köradatok a stratégiához (gumik, pitstopok)
def _load_laps(name):
    p = BASE / "data" / name
    if not p.exists():
        print(name, "-> NINCS MEG, a gumi ábra nem jelenik meg")
        return None
    want = {"Driver", "LapNumber", "LapTime", "PitOutTime", "PitInTime", "Compound",
            "TyreLife", "Stint", "TrackStatus", "IsAccurate", "RoundNumber", "Race Type"}
    d = pd.read_csv(p, usecols=lambda c: c in want)
    if "Race Type" in d.columns:                 
        d = d[d["Race Type"] == "Sprint Race"]
    for c in ("LapTime", "PitOutTime", "PitInTime"):
        if c in d.columns:
            d[c] = pd.to_timedelta(d[c], errors="coerce")
    d["LapSec"] = d["LapTime"].dt.total_seconds()
    return d

LAPS = {k: _load_laps(f) for k, f in LAPS_FILES.items() if k in SESS}
LAPS = {k: v for k, v in LAPS.items() if v is not None}
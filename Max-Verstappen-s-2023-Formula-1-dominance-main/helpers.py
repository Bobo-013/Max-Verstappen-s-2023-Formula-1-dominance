import time

import pandas as pd
from dash import dcc, html

from config import ANTHEM_DELAY, BG, MUTED, RED, TEXT
from data import SESS, d_cum, drivers, t_cum, teams


# Egy kör TrackStatus értékéből megszakítás-típus.
def _track_class(v):
    try:
        s = str(int(float(v)))
    except (TypeError, ValueError):
        return None
    if "5" in s:
        return "RED"
    if "4" in s:
        return "SC"
    if "6" in s or "7" in s:
        return "VSC"
    if "2" in s:
        return "YELLOW"
    return None

def _rgba(hex_color, a):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r},{g},{b},{a})"

# Egymást követő, azonos típusú körök összevonása: [(első kör, utolsó kör, típus), ...]
def _status_runs(d):
    runs, cur, start, prev = [], None, None, None
    for lap, cls in zip(d["LapNumber"].astype(int), d["TrackStatus"].map(_track_class)):
        if cls is not None and cls == cur and lap == prev + 1:
            prev = lap
            continue
        if cur is not None:
            runs.append((start, prev, cur))
        cur, start, prev = cls, lap, lap
    if cur is not None:
        runs.append((start, prev, cur))
    return runs
 
# 3. Közös segédek metódusok
# ---------------------------------------------------------- Színek
def _shade(hex_color, factor):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    target = 255 if factor > 0 else 0
    f = abs(factor)
    r, g, b = (round(c + (target - c) * f) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"
 
 
# Egy szín világossága 0 és 1 között.
def _luma(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255
 
 
# A csapattársak sorrendje csapaton belül (0 = első).
_team_rank = {}
for _, grp in drivers.groupby("TeamColor", sort=False):
    for i, a in enumerate(grp["Abbreviation"]):
        _team_rank[a] = i
 
 
# A CSV-beli csapatszínt átalakítása hex kóddá.
def _hex(team_color):
    h = str(team_color).strip().lstrip("#")
    if h.endswith(".0"):
        h = h[:-2]
    return "#" + h.zfill(6)
 
 
# A pilóta megjelenítési színe
def pick_color(abbr, team_color):
    base = _hex(team_color)
    rank = _team_rank.get(abbr, 0)
    if rank == 0:
        return base
    step = 0.40 if rank == 1 else 0.65
    try:
        return _shade(base, -step if _luma(base) > 0.6 else step)
    except ValueError:
        return base

# Himnusz indító
def _anthem_marker(src):
    return html.Div(id="anthem-trigger", style={"display": "none"},
                    **{"data-src": src, "data-delay": str(ANTHEM_DELAY),
                       "data-token": str(time.time_ns())})
 
# ---------------------------------------------------------- Formázás
# Helyezés szövegesen
def fmt_pos(value):
    return f"P{int(value)}" if pd.notna(value) and value > 0 else "–"
 
 
# Egy érték keresése a futam összefoglalóból, formázva.
def _get(rn, col, fmt="{}", suffix="", s="R"):
    try:
        v = SESS[s]["summary"].loc[rn, col]
    except KeyError:
        return "–"
    if pd.isna(v):
        return "–"
    return fmt.format(v) + suffix
 
 
# Szöveg -> másodperc
def to_sec(t):
    if not isinstance(t, str) or ":" not in t:
        return None
    m, s = t.split(":")
    return int(m) * 60 + float(s)

def fmt_lap(sec):
    return f"{int(sec // 60)}:{sec % 60:06.3f}" if sec is not None else "–"

def lap_sec(rn, col, s="R"):
    sm = SESS[s]["summary"]
    if col not in sm.columns:
        return None
    v = sm.loc[rn, col]
    if isinstance(v, pd.Timedelta):
        return v.total_seconds()
    return to_sec(_get(rn, col, s=s))

def num_facts(rn, s="R"):
    res = SESS[s]["results"]
    res = res[res["RoundNumber"] == rn]
    ver = res[res["Abbreviation"] == "VER"]
    sm = SESS[s]["summary"]
    row = sm.loc[rn]

    def num(col):
        if col not in sm.columns or pd.isna(row[col]):
            return None
        return float(row[col])

    def pos(col):
        if ver.empty or col not in ver.columns or pd.isna(ver.iloc[0][col]) or ver.iloc[0][col] <= 0:
            return None
        return float(ver.iloc[0][col])

    return {
        "air": num("air_temp"), "track": num("track_temp"),
        "humidity": num("humidity"), "wind": num("wind_speed"),
        "grid": pos("GridPosition"), "finish": pos("Position"),
    }
 
# ---------------------------------------------------------- Bajnoki állás
# Az állás táblázata. Ha round_no meg van adva, az adott futam utáni
# pontokkal számol, különben a szezon végi állást adja.
# mode: "drivers" vagy "teams"
def standings(mode: str, round_no=None) -> pd.DataFrame:
    table = drivers if mode == "drivers" else teams
    key = "Abbreviation" if mode == "drivers" else "TeamName"
    cum = d_cum if mode == "drivers" else t_cum
    t = table.copy()
    if round_no is not None:
        after = cum.loc[:round_no].iloc[-1]
        t["TotalPoints"] = t[key].map(after)
        t = t.sort_values("TotalPoints", ascending=False, kind="stable")
    return t
 
 
# ---------------------------------------------------------- UI építőelemek
# Pilóták / Konstruktőrök választó rádiógomb
def mode_radio(component_id: str):
    return dcc.RadioItems(
        id=component_id,
        options=[{"label": " Pilóták", "value": "drivers"},
                 {"label": " Konstruktőrök", "value": "teams"}],
        value="drivers", inline=True,
        inputStyle={"marginLeft": "16px", "accentColor": RED},
        labelStyle={"color": TEXT},
    )
 
 
# Csempék (felirat, nagy érték, kis alcím)
def tile(label, value, sub=None, color=TEXT):
    return html.Div(style={"background": BG, "padding": "12px 14px", "borderRadius": "6px"}, children=[
        html.Div(label, style={"color": MUTED, "fontSize": "11px", "textTransform": "uppercase",
                               "letterSpacing": "1px"}),
        html.Div(value, style={"fontSize": "24px", "fontWeight": "900", "fontStyle": "italic", "color": color}),
        html.Div(sub or "", style={"color": MUTED, "fontSize": "12px", "minHeight": "16px"}),
    ])
 
 
# Csempék rácsba rendezése
def tile_grid(children):
    return html.Div(children=children, style={
        "display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(170px, 1fr))", "gap": "10px"})
 
 
# Piros, nagybetűs szakaszcím
def section_title(text):
    return html.H4(text, style={"margin": "20px 0 10px", "textTransform": "uppercase", "color": RED,
                                "fontSize": "13px", "letterSpacing": "1px"})
 
 
# Egy "felirat ........ érték" sor
def stat_row(label, value, size=18):
    return html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "baseline",
                           "padding": "8px 0", "borderBottom": "1px solid #2E2E3E", "gap": "10px"}, children=[
        html.Div(str(label), style={"color": MUTED, "fontSize": "13px"}),
        html.Div(str(value), style={"fontSize": f"{size}px", "fontWeight": "900", "fontStyle": "italic"}),
    ])
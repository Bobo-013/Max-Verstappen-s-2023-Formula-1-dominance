import time
import json
from pathlib import Path
 
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import ALL, Dash, Input, Output, State, ctx, dcc, html
from dash.exceptions import PreventUpdate
from plotly.subplots import make_subplots
 
 
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

# Győztes pilóta -> himnusz fájlneve (assets/anthems/<kód>.mp3)
WINNER_ANTHEM = {"VER": "nl", "PER": "mx", "SAI": "es", "LEC": "mc", "HAM": "gb", "PIA": "au"}
TEAM_ANTHEM = {"Red Bull Racing": "at", "Ferrari": "it", "Mercedes": "de", "McLaren": "gb"}
# Pontállás-sávok (futamoldal): egy sor magassága (px), és hány másodperc késleltetés
LAP_ROW_H = 34
LAP_DELAY = 2.4
 
# Közös stílusok
card = {"background": PANEL, "padding": "20px", "borderRadius": "8px"}
header_row = {"display": "flex", "justifyContent": "space-between", "alignItems": "center"}
 
 
# 2. Adatok betöltése
BASE = Path(__file__).resolve().parent
P = BASE / "data" / "processed"
print("Projekt mappa:", BASE)

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
 
 
# 4. Közös diagramok és kártyák (főoldal és futamoldal is használja)
 
# A pontok alakulása vonaldiagramon. mode: "drivers" / "teams".
# Ha upto meg van adva, csak az adott futamig rajzol.
def build_line_chart(mode: str, upto=None) -> go.Figure:
    if mode == "drivers":
        table, cum, key, name_col = drivers, d_cum, "Abbreviation", "Abbreviation"
    else:
        table, cum, key, name_col = teams, t_cum, "TeamName", "TeamName"
 
    def cut(s):
        return s if upto is None else s.loc[:upto]
 
    fig = go.Figure()
    for _, row in table.iterrows():
        series = cut(cum[row[key]])
        x = [0] + [int(r) for r in series.index]
        y = [0] + series.tolist()
        hover = ["Szezonrajt"] + [round_names.get(int(r), "") for r in series.index]
        is_ver = mode == "drivers" and row["Abbreviation"] == "VER"
 
        # Pilótáknál a csapattárs pontozott vonalat kap
        if mode == "drivers":
            color = pick_color(row["Abbreviation"], row["TeamColor"])
            dash = "dot" if _team_rank.get(row["Abbreviation"], 0) > 0 else "solid"
        else:
            color = _hex(row["TeamColor"])
            dash = "solid"
 
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines+markers", name=row[name_col],
            line=dict(color=color, width=3 if is_ver else 2.5, dash=dash),
            marker=dict(
                size=[0] + [12 if is_ver else 8] * len(series),
                color=color,
                line=dict(color=PANEL, width=1),
            ),
            customdata=hover,
            hovertemplate=("<b>%{fullData.name}</b><br>"
                           "%{customdata}<br>"
                           "<b>%{y:.0f} pont</b><extra></extra>"),
            cliponaxis=False,
        ))
 
    fig.update_layout(
        paper_bgcolor=PANEL, plot_bgcolor=PANEL, font=dict(color=TEXT, family=FONT),
        margin=dict(l=0, r=0, t=0, b=0), height=520,
        hoverlabel=dict(font_size=15, font_family=FONT),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.01, y=0.01, yanchor="bottom"),
    )
    fig.update_xaxes(gridcolor="#2E2E3E")
    fig.update_yaxes(gridcolor="#2E2E3E")
    return fig
 
 
# ---------------------------------------------------------- Eredmény kártya.
# A header=True a futam címét is kiírja (oldalsáv).
def _best_txt(r):
    b = r.get("Best")
    return b if isinstance(b, str) and b else "–"

def race_detail(round_no: int, header: bool = True, s: str = "R"):
    ev = events[events["RoundNumber"] == round_no].iloc[0]
    res = SESS[s]["results"]
    res = res[res["RoundNumber"] == round_no].sort_values("Position")
    top3 = res.head(3).reset_index(drop=True)

    rows = []
    for i, r in top3.iterrows():
        color = pick_color(r["Abbreviation"], r["TeamColor"])
        right = _best_txt(r) if s == "Q" else f"{r['Points']:.0f} p"
        rows.append(html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px",
                                    "padding": "8px 0", "borderBottom": "1px solid #2E2E3E"}, children=[
            html.Div(str(i + 1), style={"fontSize": "26px", "fontWeight": "900", "fontStyle": "italic",
                                        "color": color, "width": "28px"}),
            html.Div(children=[
                html.Div(r["FullName"], style={"fontWeight": "700"}),
                html.Div(r["TeamName"], style={"color": MUTED, "fontSize": "12px"}),
            ]),
            html.Div(right, style={"marginLeft": "auto", "fontWeight": "700"}),
        ]))

    ver = res[res["Abbreviation"] == "VER"]
    ver_line = ""
    if not ver.empty:
        v = ver.iloc[0]
        if s == "Q":
            ver_line = f"Verstappen: {fmt_pos(v['Position'])} · {_best_txt(v)}"
        else:
            ver_line = f"Verstappen: {fmt_pos(v['GridPosition'])} → {fmt_pos(v['Position'])}"

    head = []
    if header:
        head = [
            html.Div(f"{int(ev['RoundNumber'])}. forduló", style={"color": RED, "fontWeight": "700",
                                                                  "textTransform": "uppercase", "fontSize": "12px"}),
            html.H3(ev["EventName"], style={"margin": "2px 0"}),
            html.Div(f"{ev['Location']}, {ev['Country']} · {str(ev['EventDate'])[:10]}",
                     style={"color": MUTED, "fontSize": "13px", "marginBottom": "12px"}),
        ]
    return html.Div(children=[
        *head,
        *rows,
        html.Div(ver_line, style={"marginTop": "14px", "fontWeight": "700", "color": RED}),
    ])

# Időmérő · Sprint · Futam váltó (csak akkor jelenik meg, ha az adott fordulóban több session van)
def session_tabs(rn, s):
    tabs = []
    for k in ("Q", "S", "R"):
        if k not in SESS or rn not in SESS[k]["rounds"]:
            continue
        on = k == s
        tabs.append(dcc.Link(SESS[k]["label"], href=sess_url(rn, k), style={
            "padding": "5px 14px", "borderRadius": "999px", "fontSize": "12px", "fontWeight": "700",
            "textTransform": "uppercase", "textDecoration": "none",
            "background": RED if on else BG, "color": TEXT if on else MUTED,
            "border": f"1px solid {RED if on else '#2E2E3E'}"}))
    if len(tabs) < 2:
        return html.Div()
    return html.Div(tabs, style={"display": "flex", "gap": "8px", "marginBottom": "14px"})
 
 
# ---------------------------------------------------------- Dobogó
# (helyezés, hányadik elem a listában, oszlopmagasság)
PODIUM_ORDER = [(2, 1, 110), (1, 0, 160), (3, 2, 80)]


# A dobogó három oszlopa egy sorban. Elemek: (név, alcím, érték szöveg, szín)
def _podium_row(items, extra=()):
    return html.Div(
        style={"display": "flex", "gap": "12px", "alignItems": "flex-end", "minHeight": "270px"},
        children=[*extra,
                  *[podium_block(place, *items[idx], height)
                    for place, idx, height in PODIUM_ORDER if idx < len(items)]],
    )


# Bajnoki dobogó (főoldal). mode: "drivers" / "teams".
# Ha round_no meg van adva, az akkori állást mutatja.
def podium(mode: str = "drivers", round_no=None, anthem=False):
    top = standings(mode, round_no).head(3).reset_index(drop=True)
    if mode == "drivers":
        items = [
            (r["FullName"], r["TeamName"], f"{r['TotalPoints']:.0f} pont",
             pick_color(r["Abbreviation"], r["TeamColor"]))
            for _, r in top.iterrows()
        ]
    else:
        items = [
            (r["TeamName"], "Konstruktőr", f"{r['TotalPoints']:.0f} pont", "#" + r["TeamColor"])
            for _, r in top.iterrows()
        ]
    extra = []
    if anthem and not top.empty:
        first = top.iloc[0]
        src = (anthem_for(first["Abbreviation"]) if mode == "drivers"
               else team_anthem_for(first["TeamName"]))
        extra = [_anthem_marker(src)]
    return _podium_row(items, extra=extra)


# A dobogó egy oszlopa a felirattal
def podium_block(place: int, name: str, subtitle: str, value: str, color: str, height: int):
    d = PODIUM_DELAY[place]
    return html.Div(style={"flex": "1", "textAlign": "center", "alignSelf": "flex-end"}, children=[
        html.Div(className="podium-text", style={"animationDelay": f"{d + 0.3}s"}, children=[
            html.Div(name, style={"fontWeight": "700", "fontSize": "18px"}),
            html.Div(subtitle, style={"color": MUTED, "fontSize": "13px", "marginBottom": "6px"}),
            html.Div(value, style={"color": color, "fontWeight": "700", "marginBottom": "8px"}),
        ]),
        # az oszlop nulláról nő a célmagasságig
        html.Div(str(place), className="podium-bar", style={
            "height": f"{height}px", "animationDelay": f"{d}s",
            "background": f"linear-gradient(180deg, {color}, #00000055)",
            "borderRadius": "6px 6px 0 0", "fontSize": "52px", "fontWeight": "900",
            "fontStyle": "italic", "paddingTop": "10px", "overflow": "hidden",
        }),
    ])


# A himnusz fájl elérési útja
def _anthem_path(code) -> str:
    if code and (BASE / "assets" / "anthems" / f"{code}.mp3").exists():
        return f"/assets/anthems/{code}.mp3"
    return ""


# A himnusz egy pilótához
def anthem_for(abbr) -> str:
    return _anthem_path(WINNER_ANTHEM.get(abbr))


# A himnusz egy csapathoz
def team_anthem_for(team) -> str:
    return _anthem_path(TEAM_ANTHEM.get(team))


# Egy session (futam / sprint / időmérő) első 3 helyezettje.
# Elemek: (név, alcím, érték szöveg, szín, pilóta rövidítése)
def session_standings(rn: int, s: str = "R", mode: str = "drivers"):
    res = SESS[s]["results"]
    res = res[res["RoundNumber"] == rn].copy()
    res["Position"] = pd.to_numeric(res["Position"], errors="coerce")
    res = res[res["Position"] > 0].sort_values("Position")

    if mode == "drivers":
        return [(r["FullName"], r["TeamName"],
                 _best_txt(r) if s == "Q" else f"{r['Points']:.0f} pont",
                 pick_color(r["Abbreviation"], r["TeamColor"]), r["Abbreviation"])
                for _, r in res.head(3).iterrows()]

    # Konstruktőrök: a győztes pilóta csapata az első, utána a session pontjai szerint
    rows = []
    for team, grp in res.groupby("TeamName", sort=False):
        best = grp.iloc[0]                      # a csapat legjobb helyezettje
        pts = grp["Points"].sum() if "Points" in grp.columns else 0
        rows.append((team, pts, best))

    win_team = res.iloc[0]["TeamName"] if not res.empty else None
    if s == "Q":
        rows.sort(key=lambda x: x[2]["Position"])
    else:
        rows.sort(key=lambda x: (x[0] != win_team, -x[1], x[2]["Position"]))

    return [(team, "Konstruktőr",
             _best_txt(best) if s == "Q" else f"{pts:.0f} pont",
             _hex(best["TeamColor"]), best["Abbreviation"])
            for team, pts, best in rows[:3]]

# A futamoldal dobogója: az adott session eredménye + a himnusz jelölő eleme.
# Himnusz: pilótáknál a győztesé, konstruktőrnél a győztes csapat legjobb pilótájáé.
def session_podium(mode: str, rn: int, s: str = "R"):
    items = session_standings(rn, s, mode)
    if not items:
        src = ""
    elif mode == "teams":
        src = team_anthem_for(items[0][0])
    else:
        src = anthem_for(items[0][4])
    return _podium_row([it[:4] for it in items], extra=[_anthem_marker(src)])

 
# 5. FŐOLDAL
# ---------------------------------------------------------- Földgömb
# A forgatást a böngészőben futó JS végzi.
def build_globe() -> go.Figure:
    fig = go.Figure()
    ver_wins = events[events["Winner"] == "Max Verstappen"]
    others = events[events["Winner"] != "Max Verstappen"]
 
    for df, name, color in [(ver_wins, "Verstappen-győzelem", RED), (others, "Más győztes", "#FFFFFF")]:
        fig.add_trace(go.Scattergeo(
            lon=df["Lon"], lat=df["Lat"], mode="markers", name=name,
            text=df["EventName"],
            customdata=df[["RoundNumber", "Winner"]].values,
            marker=dict(size=12, color=color, line=dict(color=BG, width=1.5)),
            hovertemplate="<b>%{text}</b><br>Győztes: %{customdata[1]}<extra></extra>",
        ))
 
    fig.update_geos(
        projection_type="orthographic",
        projection_rotation=dict(lon=START_LON, lat=START_LAT, roll=1),
        showland=True, landcolor="#33334A",
        showocean=True, oceancolor="#15151E",
        showcountries=True, countrycolor="#4A4A64",
        showcoastlines=True, coastlinecolor="#4A4A64",
        showlakes=False, showframe=False, bgcolor=PANEL,
    )
    fig.update_layout(
        paper_bgcolor=PANEL, font=dict(color=TEXT, family=FONT),
        margin=dict(l=0, r=0, t=0, b=0), height=520,
        hoverlabel=dict(font_size=15, font_family=FONT),
        legend=dict(bgcolor="rgba(0,0,0,0)", x=0.01, y=0.01, yanchor="bottom"),
    )
    return fig
 
 
# ---------------------------------------------------------- Oldalsáv
# Az oldalsáv alapállapota: Verstappen szezonstatisztikái.
def season_stats_children():
    rows = [stat_row(LABELS.get(key, key), value, 20) for key, value in stats.items()]
    return [
        html.H3("Verstappen 2023", style={"marginTop": 0, "textTransform": "uppercase"}),
        *rows,
        html.Div("Vidd az egeret egy futam fölé a részletekért.",
                 style={"color": MUTED, "fontSize": "12px", "marginTop": "12px"}),
    ]
 
 
# Az oldalsáv panelje (a tartalmát a földgömb hover callbackje cseréli).
def side_panel():
    return html.Div(id="side-panel",
                    style={"background": PANEL, "padding": "20px", "borderRadius": "8px"},
                    children=season_stats_children())
 
 
# Az oldalsáv tartalma, amikor a földgömb egy futama fölött áll az egér:
# eredménykártya + Verstappen leggyorsabb köre, időjárás, hőmérséklet.
def hover_panel_children(rn: int):
    track = _get(rn, "track_temp", "{:.0f}")
    air = _get(rn, "air_temp", "{:.0f}")
    return [
        race_detail(rn),
        html.Div(style={"marginTop": "10px"}, children=[
            stat_row("Verstappen leggyorsabb köre", _get(rn, "ver_best"), 22),
            stat_row("Időjárás", _get(rn, "condition"), 22),
            stat_row("Aszfalt / levegő", f"{track} / {air} °C", 22),
        ]),
        html.Div("Kattints a futamra a részletes oldalért →",
                 style={"color": MUTED, "fontSize": "12px", "marginTop": "12px"}),
    ]
 
# ---------------------------------------------------------- Főoldal elrendezés
def home_layout():
    return html.Div(className="page-left", children=[
        html.Div(style={"borderLeft": f"8px solid {RED}", "paddingLeft": "16px", "marginBottom": "24px"}, children=[
            html.H1("Max Verstappen 2023-as Forma 1-es dominanciája",
                    style={"margin": 0, "fontStyle": "italic", "textTransform": "uppercase"}),
            html.Div("avagy egy rekorddöntő szezon statisztikája", style={"color": MUTED}),
        ]),
        html.Div(style={"display": "flex", "gap": "24px", "alignItems": "flex-start"}, children=[
            html.Div(style={"flex": "3", "display": "flex", "flexDirection": "column", "gap": "24px"}, children=[
                # Földgömb
                html.Div(style=card, children=[
                    html.H3("A 2023-as naptár", style={"marginTop": 0, "textTransform": "uppercase"}),
                    html.Div("Vidd az egeret egy futam fölé és kattints a részletes adatokért.",
                             style={"color": MUTED, "fontSize": "13px", "marginBottom": "8px"}),
                    dcc.Graph(id="globe", figure=build_globe(), config={"displayModeBar": False}),
                ]),
                # Dobogó
                html.Div(style=card, children=[
                    html.Div(style=header_row, children=[
                        html.H3("Végeredmény", style={"margin": 0, "textTransform": "uppercase"}),
                        mode_radio("podium-mode"),
                    ]),
                    html.Div(id="podium-container", style={"marginTop": "20px"}, children=podium("drivers")),
                ]),
                # Vonaldiagram
                html.Div(style=card, children=[
                    html.Div(style=header_row, children=[
                        html.H3("Összetett bajnokság alakulása", style={"margin": 0, "textTransform": "uppercase"}),
                        mode_radio("mode"),
                    ]),
                    dcc.Graph(id="line-chart", config={"displayModeBar": False}),
                ]),
            ]),
            # Oldalsáv
            html.Div(style={"flex": "1", "minWidth": "260px"}, children=[side_panel()]),
        ]),
    ])
 
 
# 6. FUTAMOLDAL
 
# ---------------------------------------------------------- Köridők
# A kiválasztott pilóták leggyorsabb körei oszlop diagramon
# Elemek: (cím, alcím, időszöveg, másodperc, szín). A köridő nélküli sorok kiesnek.
def lap_rows_data(rn, s="R"):
    rows = []
    res_all = SESS[s]["results"]
    entries = tel_entries(rn, s, need_file = False)
    for e in entries:
        rows.append((e["name"], f"leggyorsabb kör · {e['pos']} · {e['lapno']}. kör",
                     e["laptime"], e["color"]))

    # A futam leggyorsabb köre, ha az a pilóta még nincs a listában
    fd_abbr = _get(rn, "fastest_driver", s=s)
    fast_time = _get(rn, "fastest_time", s=s)
    if to_sec(fast_time) is not None and fd_abbr not in [e["abbr"] for e in entries]:
        res = res_all[(res_all["RoundNumber"] == rn) & (res_all["Abbreviation"] == fd_abbr)]
        if not res.empty:
            r = res.iloc[0]
            color = pick_color(fd_abbr, r["TeamColor"])
            pos = fmt_pos(r["Position"])
        else:
            color, pos = "#6B6B7B", "–"
        try:
            lap_txt = f" · {int(float(_get(rn, 'fastest_lap_no', s=s)))}. kör"
        except ValueError:
            lap_txt = ""
        rows.append((NAMES.get(fd_abbr, fd_abbr),
                     f"{SESS[s]['art']} leggyorsabb köre · {pos}{lap_txt}",
                     fast_time, color))

    ver_color = pick_color("VER", drivers.loc[drivers["Abbreviation"] == "VER", "TeamColor"].iloc[0])
    rows += [
        ("Max Verstappen", "átlagos körideje", _get(rn, "ver_avg", s=s), ver_color),
        ("Mezőny", "átlagos körideje", _get(rn, "avg_all", s=s), "#6B6B7B"),
    ]
    return [(n, sub, t, to_sec(t), c) for n, sub, t, c in rows if to_sec(t) is not None]
 
 
# A sávok felépítése
# Visszaad: a megjelenítendő elemek listája, vagy None, ha nincs adat.
def lap_axis(rounds, s="R"):
    secs = []
    for r in rounds:
        secs += [row[3] for row in (lap_rows_data(r, s) or [])]
        fs = to_sec(_get(r, "fastest_time", s=s))
        if fs is not None:
            secs.append(fs)
    if not secs:
        return 0, 1
    lo, hi = min(secs), max(secs)
    pad = max((hi - lo) * 0.3, 0.5)
    return lo - pad, hi + pad * 1.5

def lap_bars(rn, wrap_id="lap-wrap", axis=None, s="R"):
    rows = lap_rows_data(rn, s)
    if not rows:
        return None

    fd = NAMES.get(_get(rn, "fastest_driver", s=s), _get(rn, "fastest_driver", s=s))
    fast_lap = _get(rn, "fastest_lap_no", s=s)
    fast_time = _get(rn, "fastest_time", s=s)
    fast_sec = to_sec(fast_time)

    axis_lo, axis_hi = axis if axis is not None else lap_axis([rn], s)

    def frac(v):
        return (v - axis_lo) / (axis_hi - axis_lo) * 100

    order = sorted(range(len(rows)), key=lambda i: rows[i][3])
    sorted_pos = {i: k for k, i in enumerate(order)}

    html_rows = []
    for i, (name, sub, t, sec, color) in enumerate(rows):
        track = [
            html.Div(className="lap-bar", style={
                "width": f"{frac(sec):.1f}%",
                "background": f"linear-gradient(180deg, {color}, #00000055)"}),
            html.Div(t, className="lap-time"),
        ]
        if fast_sec is not None:
            track.append(html.Div(className="lap-fast",
                                  style={"left": f"{frac(fast_sec):.1f}%"}))
        html_rows.append(html.Div(
            className=f"lap-row a-{i} s-{sorted_pos[i]}",
            style={"height": f"{LAP_ROW_H - 8}px"}, children=[
                html.Div(className="lap-name", children=[
                    html.Div(name, style={"fontWeight": "700"}),
                    html.Div(sub, style={"color": MUTED, "fontSize": "11px"}),
                ]),
                html.Div(className="lap-track", children=track),
            ]))

    out = []
    if fast_sec is not None:
        try:
            lap_txt = f" · {int(float(fast_lap))}. kör"
        except ValueError:
            lap_txt = ""
        who = f" ({fd}{lap_txt})" if fd and fd != "–" else ""
        out.append(html.Div(
            f"A futam leggyorsabb köre: {fast_time}{who}",
            style={"fontSize": "13px", "color": MUTED, "margin": "4px 0 14px"}))
    out.append(html.Div(id=wrap_id, className="lap-wrap",
                        style={"height": f"{len(rows) * LAP_ROW_H}px"}, children=html_rows))
    return out
 
# A "Köridők" szakasz: cím, magyarázat, rendező jelölőnégyzet és a sávok (vagy üzenet, ha nincs adat).
def lap_section(rn, s="R"):
    parts = lap_bars(rn, s=s)
    if parts is None:
        return [section_title("Köridők"),
                html.Div("Nincs köridő ehhez a futamhoz.", style={"color": MUTED})]
    return [
        section_title("Köridők"),
        html.Div("Az első 3 helyezett és Verstappen legjobb köridejének, valamint a mezőny átlagos köridejének összehasonlítása",
                 style={"color": MUTED, "fontSize": "12px", "marginBottom": "6px"}),
        dcc.Checklist(
            id="lap-sort",
            options=[{"label": " Rendezés köridő szerint (leggyorsabb elöl)", "value": "sorted"}],
            value=[], inputStyle={"accentColor": RED}, labelStyle={"color": TEXT},
            style={"marginBottom": "12px"}),
        *parts,
    ]

# ---------------------------------------------------------- Időmérő idők
# Az első 3 és Verstappen legjobb ideje sávokon, alatta a Q1 / Q2 / Q3 idők.
def quali_section(rn):
    res = SESS["Q"]["results"]
    res = res[res["RoundNumber"] == rn].sort_values("Position")
    pick = res.head(3)["Abbreviation"].tolist()
    if "VER" not in pick:
        pick.append("VER")
    sel = res[res["Abbreviation"].isin(pick) & res["BestSec"].notna()]
    title = section_title("Időmérő idők")
    if sel.empty:
        return [title, html.Div("Nincs időadat ehhez az időmérőhöz.", style={"color": MUTED})]

    secs = sel["BestSec"].astype(float).tolist()
    lo, hi = min(secs), max(secs)
    pad = max((hi - lo) * 0.3, 0.5)
    a_lo, a_hi = lo - pad, hi + pad * 1.5

    def frac(v):
        return (v - a_lo) / (a_hi - a_lo) * 100

    bars = []
    for i, (_, r) in enumerate(sel.iterrows()):
        color = pick_color(r["Abbreviation"], r["TeamColor"])
        bars.append(html.Div(className=f"lap-row a-{i}", style={"height": f"{LAP_ROW_H - 8}px"}, children=[
            html.Div(className="lap-name", children=[
                html.Div(r["FullName"], style={"fontWeight": "700"}),
                html.Div(f"{r['BestStage']} · {fmt_pos(r['Position'])}",
                         style={"color": MUTED, "fontSize": "11px"})]),
            html.Div(className="lap-track", children=[
                html.Div(className="lap-bar", style={
                    "width": f"{frac(r['BestSec']):.1f}%",
                    "background": f"linear-gradient(180deg, {color}, #00000055)"}),
                html.Div(_best_txt(r), className="lap-time"),
                html.Div(className="lap-fast", style={"left": f"{frac(lo):.1f}%"}),
            ])]))

    pole = sel.loc[sel["BestSec"].idxmin()]
    detail = [stat_row(r["FullName"],
                       " · ".join(f"{k} {r[k]}" for k in ("Q1", "Q2", "Q3")
                                  if isinstance(r[k], str) and r[k]),
                       14)
              for _, r in sel.iterrows()]
    return [
        title,
        html.Div(f"Leggjobb idő: {_best_txt(pole)} ({pole['FullName']})",
                 style={"fontSize": "13px", "color": MUTED, "margin": "4px 0 14px"}),
        html.Div(className="lap-wrap", style={"height": f"{len(bars) * LAP_ROW_H}px"}, children=bars),
        section_title("Szakaszok (Q1 · Q2 · Q3)"),
        *detail,
    ]
 
# ---------------------------------------------------------- Időjárás
CRITERIA = {
    "condition": ("condition",  "Időjárás",      ""),
    "air":       ("air_temp",   "Levegő",        " °C"),
    "track":     ("track_temp", "Aszfalt",       " °C"),
    "humidity":  ("humidity",   "Páratartalom",  " %"),
    "wind":      ("wind_speed", "Szél",          " m/s"),
}
CRITERIA = {k: v for k, v in CRITERIA.items() if v[0] in summary.columns}
TOL = 0.15

#Kattintható időjárás kártyák a futam oldalon
def wx_card(key, rn, active, s="R"):
    col, label, unit = CRITERIA[key]
    on = key in active
    return html.Div(
        [html.Div(label, style={"fontSize": "12px", "color": MUTED}),
         html.Div(_get(rn, col, "{:.0f}" if key != "condition" else "{}", unit, s=s),
                  style={"fontSize": "24px", "color": TEXT, "padding":"8px", "fontWeight":"bold"})],
        id={"type": "wx-card", "key": key}, n_clicks=0,
        style={"cursor": "pointer", "padding": "12px 20px", "borderRadius": "8px",
               "background": BG, "display": "inline-block", "marginRight": "24px",
               "minWidth" : "180px", "textAlign" : "center",
               "border": f"2px solid {RED if on else '#2E2E3E'}"})

# idő, hőmérsékletek, nyomás, páratartalom, szél és eső
def weather_section(rn, s="R"):
    summary = SESS[s]["summary"]
    num_cols = [v[0] for v in CRITERIA.values() if v[0] != "condition" and v[0] in summary.columns]
    if (not CRITERIA or rn not in summary.index
            or (num_cols and summary.loc[rn, num_cols].isna().all())):        
        return [section_title("Időjárás"),
                html.Div("Nincs időjárási adat.", style={"color": MUTED})]
    return [
        section_title("Időjárás"),
        html.Div("A hasonló időjárású futamokat megjelenítésre kattints egy kártyára.",
                 style={"color": MUTED, "fontSize": "12px", "marginBottom": "8px"}),
        dcc.Store(id="wx-active", data=[]),
        html.Div([wx_card(k, rn, [], s) for k in CRITERIA], id="wx-cards"),
        html.Div(id="wx-similar", style={"marginTop": "14px"}),
    ]

#Hasonló időjárási adatokkal rendelkező futamok
def similar_races(rn, active, s="R"):
    summary = SESS[s]["summary"]
    cur = summary.loc[rn]
    mask = pd.Series(summary.index != rn, index=summary.index)
    for key in active:
        col = CRITERIA[key][0]
        if key == "condition":
            mask &= summary[col] == cur[col]
        else:
            mask &= (summary[col] - cur[col]).abs() <= abs(cur[col]) * TOL
    return [int(r) for r in summary.index[mask]]

# A hasonló időjárási adatokkal rendelkező futamok új oldlaon való megjelenítése

#Oszlopdiagram egységes formázása
def bar_fig(title, rounds, current, series, unit="", lap=False, reverse=False,
            fmt=None, yrange=None):
    names = [round_names[r] for r in rounds]
    ticktext = [f'<span style="color:{RED}"><b>{n}</b></span>' if r == current else n
                for r, n in zip(rounds, names)]
    fig = go.Figure()

    for i, (name, vals) in enumerate(series.items()):
        if fmt:
            hover = [fmt(v) for v in vals]
        else:
            hover = [fmt_lap(v) if lap else (f"{v:.1f}{unit}" if v is not None else "–")
                     for v in vals]
        fig.add_trace(go.Bar(
            x=names, y=vals, name=name, text=hover,
            hovertemplate="%{x}<br>" + name + ": %{text}<extra></extra>",
            marker={"color": SERIES_COLORS[i % len(SERIES_COLORS)]}))

    fig.update_xaxes(type="category", categoryorder="array", categoryarray=names,
                     tickmode="array", tickvals=names, ticktext=ticktext,
                     tickangle=-40, automargin=True,
                     tickfont={"size": 12, "color": MUTED},
                     showgrid=False, linecolor="#2E2E3E",
                     fixedrange=True)
    fig.update_yaxes(gridcolor="#2E2E3E", zerolinecolor="#2E2E3E", automargin=True,
                     ticksuffix="" if lap else unit,
                     title="s" if lap else None,
                     tickfont={"color": MUTED},
                     autorange="reversed" if reverse else True,
                     fixedrange=True)

    if lap:
        vals_all = [v for vs in series.values() for v in vs if v is not None]
        if vals_all:
            lo, hi = min(vals_all), max(vals_all)
            pad = max((hi - lo) * 0.15, 0.5)
            fig.update_yaxes(range=[lo - pad, hi + pad])
    if yrange:                                   
        fig.update_yaxes(range=list(yrange), autorange=False)

    fig.update_layout(
        title={"text": title, "font": {"size": 16, "color": TEXT}, "x": 0.02, "y": 0.95},
        font={"family": FONT, "color": TEXT},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 50, "r": 20, "t": 70, "b": 20},
        legend={"orientation": "h", "x": 1, "xanchor": "right", "y": 1.12,
                "yanchor": "bottom", "font": {"color": MUTED}},
        showlegend=len(series) > 1,
        barmode="group", bargap=0.25,
        hovermode="x unified",
        hoverlabel={"bgcolor": PANEL, "font": {"family": FONT, "color": TEXT}})
    return fig


def bar_chart(title, rounds, current, series, unit="", lap=False, reverse=False):
    fig = bar_fig(title, rounds, current, series, unit, lap, reverse)
    return html.Div(dcc.Graph(figure=fig, className="nav-chart",
                              config={"displayModeBar": False},
                              style={"height": "440px"}), style=card)

def rel_laps(rounds, s="R"):
    """Eltérés Verstappen legjobb körétől másodpercben (negatív = gyorsabb)."""
    ver_avg, field, rival = [], [], []
    for r in rounds:
        vb = lap_sec(r, "ver_best", s)

        def diff(v):
            return None if (v is None or vb is None) else v - vb

        others = [row[3] for row in (lap_rows_data(r, s) or [])
          if row[0] not in ("Max Verstappen", "Mezőny")]
        ver_avg.append(diff(lap_sec(r, "ver_avg",s)))
        field.append(diff(lap_sec(r, "avg_all", s)))
        rival.append(diff(min(others)) if others else None)
    return {"VER átlag": ver_avg, "Mezőny átlag": field, "Legjobb köridő": rival}


def _fmt_delta(v):
    return f"{v:+.3f} s" if v is not None else "–"


def lap_delta_fig(rounds, rn, s="R"):
    real = rel_laps(rounds, s)
    vals = [v for vs in real.values() for v in vs if v is not None] or [0]
    lo, hi = min(0, min(vals)), max(0, max(vals))
    pad = max((hi - lo) * 0.1, 0.2)
    return bar_fig("Eltérés Verstappen legjobb körétől (s)", rounds, rn, real,
                   unit=" s", fmt=_fmt_delta, yrange=(lo - pad, hi + pad))

def similar_laps(rounds, rn, s="R"):
    return [
        section_title("Köridők"),
        html.Div("Az értékek Verstappen futamonkénti legjobb köréhez viszonyított eltérést mutatják",
                 style={"color": MUTED, "fontSize": "12px", "marginBottom": "10px"}),
        html.Div(style=card, children=[
            dcc.Graph(id="lap-delta-graph", className="delta-anim nav-chart",
                figure=lap_delta_fig(rounds, rn, s),
                config={"displayModeBar": False}, style={"height": "440px"}),]
        )]

def similar_page(rn, keys, s="R"):
    others = similar_races(rn, keys, s)
    back = dcc.Link("← Vissza a futamhoz", href=sess_url(rn, s),
                    style={"color": RED, "fontWeight": "700", "textTransform": "uppercase",
                           "fontSize": "13px", "textDecoration": "none"})
    crit = ", ".join(CRITERIA[k][1] for k in keys) or "–"
    header = [back,
              html.H2(f"{round_names[rn]} – hasonló időjárású futamok",
                      style={"margin": "30px 0 4px"}),
              html.Div(f"Egyező adatok: {crit} · {len(others)} találat",
                       style={"color": MUTED, "marginBottom": "20px"})]

    if not others:
        return html.Div(className="page-right", children=header + [
            html.Div("Nincs ilyen hasonló futam.", style={"color": MUTED})])

    rounds = sorted([rn] + others)
    nums = {r: num_facts(r, s) for r in rounds}

    def col(k):
        return [nums[r][k] for r in rounds]

    charts = []
    if "air" in CRITERIA or "track" in CRITERIA:
        charts.append(bar_chart("Hőmérséklet", rounds, rn,
                                {"Levegő": col("air"), "Aszfalt": col("track")},
                                unit=" °C"))
    if "humidity" in CRITERIA:
        charts.append(bar_chart("Páratartalom", rounds, rn,
                                {"Páratartalom": col("humidity")}, unit=" %"))
    if "wind" in CRITERIA:
        charts.append(bar_chart("Szél", rounds, rn,
                                {"Szél": col("wind")}, unit=" m/s"))
    charts.append(bar_chart("Verstappen: rajt → cél", rounds, rn,
                            {"Rajtpozíció": col("grid"), "Célpozíció": col("finish")},
                            reverse=True))

    return html.Div(className="page-right", children=header + [
        *similar_laps(rounds, rn, s),
        html.Div(charts, style={"display": "grid", "gap": "20px", "marginTop": "20px",
                                "gridTemplateColumns": "repeat(auto-fit, minmax(480px, 1fr))"}),
    ])

# ---------------------------------------------------------- Telemetria
# Egy pilóta telemetria-fájljának útja az adott futamhoz.
def tel_path(rn, abbr, s="R"):
    return P / SESS[s]["tel_dir"] / f"round_{rn:02d}_{abbr}.csv"
 
 
# Az adott futam telemetriái a befutó sorrendjében
# (rövidítés, név, szín, köridő, körszám, helyezés).
def tel_entries(rn, s="R", need_file=True):
    ti = SESS[s]["tel_index"]
    idx = ti[ti["RoundNumber"] == rn].set_index("Driver")
    res = SESS[s]["results"]
    res = res[res["RoundNumber"] == rn].sort_values("Position")
    out = []
    for _, r in res.iterrows():
        a = r["Abbreviation"]
        if a in idx.index and (not need_file or tel_path(rn, a, s).exists()):
            out.append({
                "abbr": a,
                "name": NAMES.get(a, a),
                "color": pick_color(a, r["TeamColor"]),
                "laptime": idx.loc[a, "LapTime"],
                "lapno": int(idx.loc[a, "LapNumber"]),
                "pos": fmt_pos(r["Position"]),
            })
    return out
 
# Egy jelölőnégyzet a pilótaválasztóban
def tel_option(e):
    dot = html.Span(style={"display": "inline-block", "width": "10px", "height": "10px",
                           "borderRadius": "50%", "background": e["color"], "margin": "0 6px 0 4px", "fontSize":"18px"})
    return {"label": html.Span([dot, f"{e['abbr']} ({e['pos']}) · {e['lapno']} kör"]),
            "value": e["abbr"]}
 
 
# Ha nincs pilóta kiválasztva
def empty_fig(text):
    fig = go.Figure()
    fig.update_layout(paper_bgcolor=PANEL, plot_bgcolor=PANEL, height=200,
                      font=dict(color=TEXT, family=FONT),
                      xaxis=dict(visible=False), yaxis=dict(visible=False),
                      annotations=[dict(text=text, showarrow=False, font=dict(color=MUTED))])
    return fig
 
 
# A telemetria-diagram: időkülönbség, sebesség, gáz, fék, fokozat
# Az időkülönbség az első kijelölt pilótához képest van.
def telemetry_figure(rn, selected):
    all_entries = tel_entries(rn)
    entries = [e for e in all_entries if e["abbr"] in selected] if selected else all_entries
    if not entries:
        return empty_fig("Nincs telemetria ehhez a futamhoz.")
 
    data = {e["abbr"]: pd.read_csv(tel_path(rn, e["abbr"])) for e in entries}
 
    # Közös, 1 méteres rács a legrövidebb kör hosszáig
    end = min(d["Distance"].max() for d in data.values())
    grid = np.arange(0, end, 1)
 
    def on_grid(d, col):
        return np.interp(grid, d["Distance"], d[col])
 
    ref = entries[0]["abbr"]
    ref_time = on_grid(data[ref], "Time")
 
    # (panel címe, relatív magasság)
    panels = [(f"Időkülönbség (s) – {ref}-hez képest (+ = lassabb)", 0.22),
              ("Sebesség (km/h)", 0.32), ("Gáz (%)", 0.16),
              ("Fék", 0.12), ("Sebességfokozat", 0.18)]
 
    fig = make_subplots(rows=len(panels), cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        row_heights=[h for _, h in panels],
                        subplot_titles=[t for t, _ in panels])
 
    for e in entries:
        abbr = e["abbr"]
        d = data[abbr]
        dash = "dot" if _team_rank.get(abbr, 0) > 0 else "solid"
        line = dict(color=e["color"], width=1.5, dash=dash)
 
        # A panelek adatsorai (a fék és a fokozat lépcsős vonal)
        series = [
            (on_grid(d, "Time") - ref_time, {}),
            (on_grid(d, "Speed"), {}),
            (on_grid(d, "Throttle"), {}),
            (on_grid(d, "Brake").clip(0, 1) * 100, {"shape": "hv"}),
            (np.rint(on_grid(d, "nGear")), {"shape": "hv"}),
        ]
        for i, (y, extra) in enumerate(series, start=1):
            fig.add_trace(go.Scatter(
                x=grid, y=y,
                name=f"{NAMES.get(abbr, abbr)} · {e['lapno']}. kör",
                legendgroup=abbr,
                showlegend=(i == 1),
                line={**line, **extra},
            ), row=i, col=1)
 
    fig.update_xaxes(gridcolor="#2E2E3E")
    fig.update_yaxes(gridcolor="#2E2E3E")
    fig.update_yaxes(dtick=0.25, row=1, col=1)                          # időkülönbség
    fig.update_yaxes(dtick=20, row=2, col=1)                            # sebesség
    fig.update_yaxes(dtick=25, range=[-5, 105], row=3, col=1)           # gáz
    fig.update_yaxes(tickvals=[0, 100], ticktext=["Nem", "Fék"],
                     range=[-15, 115], row=4, col=1)                    # fék
    fig.update_yaxes(dtick=1, range=[0.5, 8.5], row=5, col=1)           # fokozat
    fig.update_xaxes(title_text="Megtett táv a körben (m)", row=len(panels), col=1)
    fig.update_layout(
        paper_bgcolor=PANEL, plot_bgcolor=PANEL, font=dict(color=TEXT, family=FONT),
        height=200 * len(panels) +80, hovermode="x unified",
        legend=dict(orientation="v", x=0, xanchor="left", y=1, yanchor="bottom", bgcolor="rgba(0,0,0,0)", font=dict(size=14, color=TEXT)),
        margin=dict(l=60, r=20, t=50, b=40))
    fig.update_annotations(font=dict(size=12, color=MUTED))
    return fig
 
 
# Magyarázat, pilótaválasztó jelölőnégyzetek és a diagram helye (a diagramot a callback tölti ki).
def telemetry_section(rn):
    entries = tel_entries(rn)
    title = section_title("Telemetria – a leggyorsabb kör")
    if not entries:
        return [title, html.Div("Nincs telemetria ehhez a futamhoz.", style={"color": MUTED})]
    return [
        title,
        html.Div("Az első 3 helyezett és Verstappen leggyorsabb köre. A jelmagyarázatra kattintva "
                 "váltogathatod a pilótákat. (Dupla kattintással izolálhatod őket)",
                 style={"color": MUTED, "fontSize": "12px", "marginBottom": "8px"}),
        dcc.Graph(id="tel-graph", config={"displayModeBar": False}),
    ]
 
# ---------------------------------------------------------- Futamoldal elrendezés
# A futamoldal kártyája: köridők + időjárás + telemetria
def build_extra(rn: int, s: str = "R"):
    if s == "Q":
        body = quali_section(rn)
    elif SESS[s]["summary"].empty:
        body = [html.Div("Futtasd előbb a dataset.py-t.", style={"color": MUTED})]
    else:
        body = lap_section(rn, s) + weather_section(rn, s)
        if s == "R":
            body += telemetry_section(rn)
    return html.Div(style=card, children=body)

# Előző / következő futam navigáció
def race_nav(rn: int):
    rounds = sorted(round_names)
    first, last = rounds[0], rounds[-1]

    def btn(text, btn_id, enabled):
        return html.Button(text, id=btn_id, n_clicks=0, disabled=not enabled, style={
            "background": "none", "border": "none", "padding": 0, "fontFamily": FONT,
            "fontWeight": "700", "textTransform": "uppercase", "fontSize": "13px",
            "color": RED if enabled else MUTED,
            "cursor": "pointer" if enabled else "default",
        })

    return html.Div(style={"display": "flex", "gap": "24px"}, children=[
        btn("← Előző futam", "prev-btn", rn > first),
        btn("Következő futam →", "next-btn", rn < last),
    ])
 
# Egy futam teljes oldala: visszagomb, cím, eredmény + bajnoki állás
# dobogó, a részletek kártya, a pontok alakulása vonaldiagramon.
def race_page(rn: int, s: str = "R"):
    title = round_names.get(rn) + ("" if s == "R" else f" · {SESS[s]['label']}")
    return html.Div(className="page-right", children=[
        html.Div(style={**header_row, "marginBottom": "10px"}, children=[
            html.Button("← Vissza a naptárhoz", id="back-btn", n_clicks=0,
                        style={"background": "none", "border": "none", "padding": 0, "cursor": "pointer",
                               "color": RED, "fontWeight": "700", "textTransform": "uppercase",
                               "fontSize": "13px", "fontFamily": FONT}),
            html.H2(title, style={"fontSize": "42px", "color": MUTED, "fontFamily": FONT, "textTransform": "uppercase"}),
            race_nav(rn),
        ]),

        html.Div(style={"display": "flex", "flexDirection": "column", "gap": "24px"}, children=[
            html.Div(style={"display": "flex", "gap": "24px", "alignItems": "stretch", "flexWrap": "wrap"}, children=[
                # Futam eredménye
                html.Div(style={**card, "flex": "1", "minWidth": "300px"}, children=[
                    html.H3(f"{SESS[s]['label']} eredménye", style={"marginTop": 0, "textTransform": "uppercase"}),
                    session_tabs(rn, s),
                    race_detail(rn, header=False, s=s),
                ]),
                # A session dobogója (nem a bajnoki állás)
                html.Div(style={**card, "flex": "2", "minWidth": "400px"}, children=[
                    html.Div(style=header_row, children=[
                        html.H3(f"{SESS[s]['label']} dobogója",
                                style={"margin": 0, "textTransform": "uppercase"}),
                        mode_radio("r-podium-mode"),
                    ]),
                    html.Div(id="r-podium-container", style={"marginTop": "20px"},
                             children=session_podium("drivers", rn, s)),
                ]),
            ]),
            # Köridők, időjárás, telemetria
            build_extra(rn, s),
            # Pontok alakulása a futamig
            html.Div(style=card, children=[
                html.Div(style=header_row, children=[
                    html.H3(f"Összpontszám a(z) {rn}. futamig", style={"margin": 0, "textTransform": "uppercase"}),
                    mode_radio("r-line-mode"),
                ]),
                dcc.Graph(id="r-line-chart", figure=build_line_chart("drivers", rn),
                          config={"displayModeBar": False}),
            ]),
        ]),
    ])
 
 
# 7. Oldalsablon: CSS animációk + földgömb-forgató JavaScript
#   - CSS: a dobogó és az oldalváltás animációi
#   - JS: a földgömb folyamatos forgatása, és a kattintáskor az oldal kicsúszása
INDEX_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <script>
        // --- Animációk CSS-e (a dobogó és az oldalváltás) ---
        (function () {
            var css = '@keyframes podium-grow { from { height: 0; padding-top: 0; } }'
                    + '@keyframes podium-fade { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }'
                    + '.podium-bar { animation: podium-grow 0.7s cubic-bezier(.2,.8,.2,1) both; }'
                    + '.podium-text { animation: podium-fade 0.5s ease-out both; }'
                    + '@keyframes bar-grow { from { transform: scaleY(0); } to { transform: scaleY(1); } }'
                    + '__DELTA_CSS__'
                    + '@keyframes page-in-right { from { opacity: 0; transform: translateX(90px); } to { opacity: 1; transform: none; } }'
                    + '@keyframes page-in-left { from { opacity: 0; transform: translateX(-90px); } to { opacity: 1; transform: none; } }'
                    + '.page-right { animation: page-in-right __PAGE_IN_S__s cubic-bezier(.2,.8,.2,1) backwards; }'
                    + '.page-left { animation: page-in-left __PAGE_IN_S__s cubic-bezier(.2,.8,.2,1) backwards; }'
                    + '@keyframes page-out-left { from { opacity: 1; transform: none; } to { opacity: 0; transform: translateX(-90px); } }'
                    + '@keyframes page-out-right { from { opacity: 1; transform: none; } to { opacity: 0; transform: translateX(90px); } }'
                    + '.page-out-left { animation: page-out-left __PAGE_OUT_S__s ease-in forwards; }'
                    + '.page-out-right { animation: page-out-right __PAGE_OUT_S__s ease-in forwards; }'
                    // >>> ÚJ: köridő-sávok CSS-e (a generált sorok helyzetéig)
                    + '@keyframes lap-fade { from { opacity: 0; } to { opacity: 1; } }'
                    + '@keyframes lap-grow { from { width: 0; } }'
                    + '.lap-wrap { position: relative; }'
                    + '.lap-row { position: absolute; top: 0; left: 0; right: 0; display: flex; align-items: center; gap: 12px; transition: transform 0.8s cubic-bezier(.2,.8,.2,1); animation: lap-fade 0.6s ease-out __LAP_DELAY__s both; }'
                    + '.lap-name { width: 210px; flex: none; font-size: 14px; line-height: 1.25; }'
                    + '.lap-track { position: relative; flex: 1; align-self: stretch; display: flex; align-items: center; gap: 10px; }'
                    + '.lap-bar { flex: none; height: 24px; min-width: 3px; border-radius: 3px 8px 8px 3px; box-shadow: 0 3px 0 rgba(0,0,0,.4), 0 6px 10px rgba(0,0,0,.35), inset 0 2px 0 rgba(255,255,255,.3); animation: lap-grow 0.9s cubic-bezier(.2,.8,.2,1) __LAP_BAR_DELAY__s both; }'
                    + '.lap-time { flex: none; font-size: 16px; font-weight: 900; font-style: italic; }'
                    + '.lap-fast { position: absolute; top: -4px; bottom: -4px; width: 3px; margin-left: -1px; background: #F2F2F2; border-radius: 2px; }'
                    + '__LAP_CSS__'
                    + 'html, body { overflow-x: hidden; }';
            var st = document.createElement('style');
            st.id = 'podium-css';
            st.textContent = css;
            document.head.appendChild(st);
        })();
 
        // --- Földgömb forgatása és a főoldal kicsúszása ---
        (function () {
            var lon = __START_LON__;
            var paused = false;
 
            // Az aktuális oldal kicsúszik (dir: 'left' vagy 'right')
            function exitPage(dir) {
                var pg = document.querySelector('#page > div');
                if (!pg || pg.classList.contains('page-out-left') || pg.classList.contains('page-out-right')) return;
                pg.classList.remove('page-left', 'page-right');
                pg.classList.add(dir === 'left' ? 'page-out-left' : 'page-out-right');
            }
 
            setInterval(function () {
                var el = document.getElementById('globe');
                var gd = el ? el.querySelector('.js-plotly-plot') : null;
 
                // Földgömb pontjára kattintás: a főoldal balra csúszik ki
                if (gd && typeof gd.on === 'function' && !gd._exitBound) {
                    gd._exitBound = true;
                    gd.on('plotly_click', function () { exitPage('left'); });
                }
                if (paused) return;
 
                // Minden tickben egy kicsit tovább forgatjuk a földgömböt
                if (gd && gd.layout && window.Plotly) {
                    lon = (lon + __STEP_DEG__) % 360;
                    window.Plotly.relayout(gd, {'geo.projection.rotation.lon': lon});
                }
            }, __INTERVAL_MS__);
        })();
        (function () {
            function mark() {
                var gd = document.querySelector('#lap-delta-graph .js-plotly-plot');
                if (!gd || !gd._fullLayout || !gd._fullLayout.yaxis) return;
                var zero = gd._fullLayout.yaxis.l2p(0);
                gd.querySelectorAll('.barlayer .point:not([data-o])').forEach(function (p) {
                    var path = p.querySelector('path');
                    if (!path) return;
                    var b = path.getBBox();
                    var atBottom = Math.abs(b.y + b.height - zero) <= Math.abs(b.y - zero);
                    p.setAttribute('data-o', atBottom ? 'b' : 't');
                });
            }
            document.addEventListener('DOMContentLoaded', function () {
                new MutationObserver(mark).observe(document.body, { childList: true, subtree: true });
            });
        })();
         (function () {
            var ROUNDS = __ROUND_NAMES__;
            var lastGraph = null;

            function tickAt(x, y) {
                var hit = null;
                document.querySelectorAll('.nav-chart .xtick text').forEach(function (t) {
                    var r = t.getBoundingClientRect();
                    if (x >= r.left - 4 && x <= r.right + 4 && y >= r.top - 4 && y <= r.bottom + 4)
                        hit = t;
                });
                return hit;
            }

            document.addEventListener('mousemove', function (e) {
                var t = tickAt(e.clientX, e.clientY);
                var g = t ? t.closest('.nav-chart') : null;
                if (lastGraph && lastGraph !== g) lastGraph.style.cursor = '';
                if (g) g.style.cursor = 'pointer';
                lastGraph = g;
            });

            document.addEventListener('click', function (e) {
                var t = tickAt(e.clientX, e.clientY);
                if (!t) return;
                var rn = ROUNDS[t.textContent.trim()];
                if (!rn) return;
                var p = location.pathname.split('/').filter(Boolean);
                var slug = p[0] === 'similar' ? (p[3] || '') : (p[2] || '');
                if (slug === 'race') slug = '';
                window.history.pushState({}, '', '/race/' + rn + (slug ? '/' + slug : ''));
                window.dispatchEvent(new PopStateEvent('popstate'));
            });
        })();
        // --- Zene: háttérzene + a győztes himnusza ---
        (function () {
            var THEME_VOL = __THEME_VOL__, ANTHEM_VOL = __ANTHEM_VOL__, ANTHEM_S = __ANTHEM_S__;
            var theme = new Audio('__THEME_FILE__');
            theme.loop = true;
            theme.volume = THEME_VOL;
            var anthem = null, anthemTimer = null, fadeTimer = null;
            var anthemActive = false;

            function playTheme() {
                if (anthemActive) return;
                theme.play().catch(function () {});
            }
            // Ha a böngésző blokkolta az automatikus indítást, az első interakció elindítja
            function startTheme() {
                if (anthemActive) return;
                theme.play().then(function () {
                    document.removeEventListener('pointerdown', startTheme);
                    document.removeEventListener('keydown', startTheme);
                }).catch(function () {});
            }
            playTheme();
            window.addEventListener('load', playTheme);
            document.addEventListener('pointerdown', startTheme);
            document.addEventListener('keydown', startTheme);

            function stopAnthem(resume) {
                clearTimeout(anthemTimer);
                clearInterval(fadeTimer);
                if (anthem) { anthem.pause(); anthem = null; }
                anthemActive = false;
                if (resume !== false) playTheme();
            }

            function fadeOut() {
                var a = anthem;
                if (!a) return;
                fadeTimer = setInterval(function () {
                    a.volume = Math.max(0, a.volume - ANTHEM_VOL / 10);
                    if (a.volume <= 0.001) stopAnthem();
                }, 100);
            }

            function playAnthem(src, delayS) {
                stopAnthem(false);
                if (!src) { playTheme(); return; }
                anthemActive = true;
                theme.pause();
                anthemTimer = setTimeout(function () {
                    var a = new Audio(src);
                    anthem = a;
                    a.volume = ANTHEM_VOL;
                    a.play().catch(function () { if (anthem === a) stopAnthem(); });
                    anthemTimer = setTimeout(fadeOut, (ANTHEM_S - 1) * 1000);
                }, delayS * 1000);
            }

            document.addEventListener('DOMContentLoaded', function () {
                var lastToken = null;
                function check() {
                    var t = document.getElementById('anthem-trigger');
                    var token = t ? t.getAttribute('data-token') : null;
                    if (token === lastToken) return;
                    lastToken = token;
                    if (t) playAnthem(t.getAttribute('data-src'),
                                      parseFloat(t.getAttribute('data-delay')) || 0);
                    else stopAnthem();
                }
                new MutationObserver(check).observe(document.body, {
                    childList: true, subtree: true,
                    attributes: true, attributeFilter: ['data-token']
                });
            });
        })();
    </script>
</head>
<body>
    {%app_entry%}
    <footer>
        {%config%}
        {%scripts%}
        {%renderer%}
    </footer>
</body>
</html>"""
 

# 8. App, útvonalválasztás és callbackek

#Köridő oszlopok rendezése
def _lap_css(max_rows=40):
    out = []
    for i in range(max_rows):
        y = i * LAP_ROW_H
        d = i * 0.03
        out.append(f".lap-row.a-{i}{{transform:translateY({y}px);transition-delay:{d:.2f}s}}")
        out.append(f".lap-sorted .lap-row.s-{i}{{transform:translateY({y}px);transition-delay:{d:.2f}s}}")
    return "".join(out)

#Oszlopok animációja
def _delta_css():
    return (".delta-anim .point[data-o]{transform-box:fill-box;"
            "animation:bar-grow 1.2s cubic-bezier(.2,.8,.2,1) 0.3s both}"
            '.delta-anim .point[data-o="b"]{transform-origin:center bottom}'
            '.delta-anim .point[data-o="t"]{transform-origin:center top}'
            ".nav-chart .nsewdrag, .nav-chart .cursor-pointer"
            "{cursor:default !important}")

app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "Verstappen 2023"
app.index_string = (INDEX_TEMPLATE
                    .replace("__START_LON__", str(START_LON))
                    .replace("__STEP_DEG__", str(STEP_DEG))
                    .replace("__INTERVAL_MS__", str(INTERVAL_MS))
                    .replace("__PAGE_IN_S__", str(PAGE_IN_S))
                    .replace("__PAGE_OUT_S__", str(PAGE_OUT_S))
                    .replace("__LAP_DELAY__", str(LAP_DELAY))
                    .replace("__LAP_BAR_DELAY__", str(LAP_DELAY + 0.2))
                    .replace("__LAP_CSS__", _lap_css())
                    .replace("__DELTA_CSS__", _delta_css())
                    .replace("__ROUND_NAMES__", json.dumps({v: int(k) for k, v in round_names.items()}))
                    .replace("__THEME_FILE__", THEME_FILE)
                    .replace("__THEME_VOL__", str(THEME_VOL))
                    .replace("__ANTHEM_VOL__", str(ANTHEM_VOL))
                    .replace("__ANTHEM_S__", str(ANTHEM_S)))
 
# Az oldal váza: egy URL-figyelő és egy hely, ahová az aktuális oldal kerül
app.layout = html.Div(style={"background": BG, "color": TEXT, "fontFamily": FONT,
                             "minHeight": "100vh", "padding": "24px 40px"}, children=[
    dcc.Location(id="url", refresh=False),
    html.Div(id="page"),
    html.Button("🔊", id="music-btn", title="Zene be/ki", style={
        "position": "fixed", "bottom": "20px", "right": "20px", "zIndex": 1000,
        "width": "44px", "height": "44px", "borderRadius": "50%", "fontSize": "18px",
        "background": PANEL, "color": TEXT, "border": "1px solid #2E2E3E", "cursor": "pointer"}),
])
 
 
# A futamszám kiolvasása az útvonalból
# Ha érvénytelen, None.
def round_from_path(path):
    try:
        rn = int(path.strip("/").split("/")[1])
        return rn if rn in round_names else None
    except (AttributeError, IndexError, ValueError):
        return None

# ---------------------------------------------------------- Útvonalválasztás
@app.callback(Output("page", "children"), Input("url", "pathname"))
def route(path):
    if path and path.startswith("/race/"):
        rn, s = round_from_path(path), session_from_path(path)
        if rn is not None and rn in SESS[s]["rounds"]:
            return race_page(rn, s)
    if path and path.startswith("/similar/"):
        rn, s = round_from_path(path), session_from_path(path)
        if rn is not None and rn in SESS[s]["rounds"] and not SESS[s]["summary"].empty:
            parts = path.strip("/").split("/")
            keys = [k for k in (parts[2].split("-") if len(parts) > 2 else []) if k in CRITERIA]
            return similar_page(rn, keys, s)

    return home_layout()

# ---------------------------------------------------------- Navigáció 
# Földgömb pontjára kattintás -> a futam oldalára ugrik
@app.callback(Output("url", "pathname", allow_duplicate=True),
              Input("globe", "clickData"), prevent_initial_call=True)
def go_to_race(click):
    if not click:
        raise PreventUpdate
    time.sleep(PAGE_OUT_S)
    return f"/race/{int(click['points'][0]['customdata'][0])}"
 
 
# "Vissza a naptárhoz" gomb -> a főoldalra ugrik
@app.callback(Output("url", "pathname", allow_duplicate=True),
              Input("back-btn", "n_clicks"), prevent_initial_call=True)
def go_home(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    time.sleep(PAGE_OUT_S)
    return "/"

# "Előző futam" gomb
@app.callback(Output("url", "pathname", allow_duplicate=True),
              Input("prev-btn", "n_clicks"), State("url", "pathname"),
              prevent_initial_call=True)
def go_prev(n_clicks, path):
    rn = round_from_path(path)
    rounds = sorted(round_names)
    if not n_clicks or rn is None or rn <= rounds[0]:
        raise PreventUpdate
    return f"/race/{rounds[rounds.index(rn) - 1]}"


# "Következő futam" gomb
@app.callback(Output("url", "pathname", allow_duplicate=True),
              Input("next-btn", "n_clicks"), State("url", "pathname"),
              prevent_initial_call=True)
def go_next(n_clicks, path):
    rn = round_from_path(path)
    rounds = sorted(round_names)
    if not n_clicks or rn is None or rn >= rounds[-1]:
        raise PreventUpdate
    return f"/race/{rounds[rounds.index(rn) + 1]}"
 
# ---------------------------------------------------------- Főoldal callbackek
# Földgömb fölé húzott egér -> az oldalsáv a futam adatait mutatja
# (ha az egér elmegy, visszaáll a szezonstatisztikára)
@app.callback(Output("side-panel", "children"), Input("globe", "hoverData"))
def hover_side(hover):
    if not hover:
        return season_stats_children()
    return hover_panel_children(int(hover["points"][0]["customdata"][0]))
 
 
# Pilóták / Konstruktőrök váltása a főoldali vonaldiagramon
@app.callback(Output("line-chart", "figure"), Input("mode", "value"))
def update_chart(mode):
    return build_line_chart(mode)
 
 
# Pilóták / Konstruktőrök váltása a főoldali dobogón
@app.callback(Output("podium-container", "children"),
              Input("podium-mode", "value"), prevent_initial_call=True)
def update_podium(mode):
    if not ctx.triggered_id:
        raise PreventUpdate
    return podium(mode, anthem=True)
 
 
# ---------------------------------------------------------- Futamoldal callbackek
# Pilóták ki-be pipálása a telemetria-diagramon
@app.callback(Output("tel-graph", "figure"), Input("url", "pathname"))
def update_telemetry(path):
    rn = round_from_path(path)
    if rn is None:
        raise PreventUpdate
    return telemetry_figure(rn, None)
 
 
# Pilóták / Konstruktőrök váltása a futamoldali vonaldiagramon
@app.callback(Output("r-line-chart", "figure"),
              Input("r-line-mode", "value"), State("url", "pathname"))
def update_race_chart(mode, path):
    rn = round_from_path(path)
    if rn is None:
        raise PreventUpdate
    return build_line_chart(mode, rn)
 
 
# Pilóták / Konstruktőrök váltása a futamoldali dobogón
@app.callback(Output("r-podium-container", "children"),
              Input("r-podium-mode", "value"), State("url", "pathname"),
              prevent_initial_call=True)
def update_race_podium(mode, path):
    rn = round_from_path(path)
    if rn is None or not ctx.triggered_id:
        raise PreventUpdate
    return session_podium(mode, rn, session_from_path(path))

# Köridők rendezése
app.clientside_callback(
    "function (value) { return (value && value.length) ? 'lap-wrap lap-sorted' : 'lap-wrap'; }",
    Output("lap-wrap", "className"),
    Input("lap-sort", "value"),
)

# Időjárás kártyák kattintása
@app.callback(Output("wx-active", "data"),
              Input({"type": "wx-card", "key": ALL}, "n_clicks"),
              State("wx-active", "data"), prevent_initial_call=True)
def toggle_criterion(_, active):
    if not ctx.triggered_id or not any(_):
        raise PreventUpdate
    key = ctx.triggered_id["key"]
    active = list(active or [])
    active.remove(key) if key in active else active.append(key)
    return active


@app.callback(Output("wx-similar", "children"), Output("wx-cards", "children"),
              Input("wx-active", "data"), State("url", "pathname"))
def show_similar(active, path):
    rn = round_from_path(path)
    s = session_from_path(path)
    if rn is None:
        raise PreventUpdate
    cards = [wx_card(k, rn, active) for k in CRITERIA]
    if not active:
        return html.Div(style={"color": MUTED}), cards

    found = similar_races(rn, active, s)
    if not found:
        return html.Div("Nincs ilyen hasonló futam.", style={"color": MUTED}), cards

    names = ", ".join(round_names[r] for r in found)
    link = dcc.Link(f"{len(found)} hasonló {SESS[s]['noun']} megnyitása és összehasonlítása →",
                    href=f"/similar/{rn}/{'-'.join(active)}/{SESS[s]['slug']}",
                    style={"color": RED, "fontWeight": "700"})
    return [html.Div(names, style={"color": MUTED, "fontSize": "13px", "marginBottom": "6px"}),
            link], cards
 
if __name__ == "__main__":
    app.run(debug=True)
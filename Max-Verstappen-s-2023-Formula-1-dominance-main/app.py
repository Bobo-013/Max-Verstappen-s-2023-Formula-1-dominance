import time
from pathlib import Path
 
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html
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

# Pontállás-sávok (futamoldal): egy sor magassága (px), és hány másodperc késleltetés
LAP_ROW_H = 34
LAP_DELAY = 2.4
 
# Közös stílusok
card = {"background": PANEL, "padding": "20px", "borderRadius": "8px"}
header_row = {"display": "flex", "justifyContent": "space-between", "alignItems": "center"}
 
 
# 2. Adatok betöltése
BASE = Path(__file__).resolve().parent
P = BASE / "data" / "processed"
 
drivers = pd.read_csv(P / "drivers.csv", dtype={"TeamColor": str})
teams = pd.read_csv(P / "teams.csv", dtype={"TeamColor": str})
d_cum = pd.read_csv(P / "driver_cumulative_points.csv", index_col=0)
t_cum = pd.read_csv(P / "team_cumulative_points.csv", index_col=0)
events = pd.read_csv(P / "events.csv")
stats = pd.read_csv(P / "verstappen_stats.csv", index_col=0)["value"]
 
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
 
 
# ---------------------------------------------------------- Formázás
# Helyezés szövegesen
def fmt_pos(value):
    return f"P{int(value)}" if pd.notna(value) and value > 0 else "–"
 
 
# Egy érték keresése a futam összefoglalóból, formázva.
def _get(rn, col, fmt="{}", suffix=""):
    try:
        v = summary.loc[rn, col]
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
def race_detail(round_no: int, header: bool = True):
    ev = events[events["RoundNumber"] == round_no].iloc[0]
    res = results[results["RoundNumber"] == round_no].sort_values("Position")
    top3 = res.head(3).reset_index(drop=True)
 
    rows = []
    for i, r in top3.iterrows():
        color = pick_color(r["Abbreviation"], r["TeamColor"])
        rows.append(html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px",
                                    "padding": "8px 0", "borderBottom": "1px solid #2E2E3E"}, children=[
            html.Div(str(i + 1), style={"fontSize": "26px", "fontWeight": "900", "fontStyle": "italic",
                                        "color": color, "width": "28px"}),
            html.Div(children=[
                html.Div(r["FullName"], style={"fontWeight": "700"}),
                html.Div(r["TeamName"], style={"color": MUTED, "fontSize": "12px"}),
            ]),
            html.Div(f"{r['Points']:.0f} p", style={"marginLeft": "auto", "fontWeight": "700"}),
        ]))
 
    ver = res[res["Abbreviation"] == "VER"]
    ver_line = ""
    if not ver.empty:
        v = ver.iloc[0]
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
 
 
# ---------------------------------------------------------- Dobogó
# mode: "drivers" / "teams". Ha round_no meg van adva, az akkori állást mutatja.
def podium(mode: str = "drivers", round_no=None):
    top = standings(mode, round_no).head(3).reset_index(drop=True)
    if mode == "drivers":
        items = [
            (r["FullName"], r["TeamName"], r["TotalPoints"], pick_color(r["Abbreviation"], r["TeamColor"]))
            for _, r in top.iterrows()
        ]
    else:
        items = [
            (r["TeamName"], "Konstruktőr", r["TotalPoints"], "#" + r["TeamColor"])
            for _, r in top.iterrows()
        ]
 
    # (helyezés, hányadik elem az állásban, oszlopmagasság)
    order = [(2, 1, 110), (1, 0, 160), (3, 2, 80)]
    return html.Div(
        style={"display": "flex", "gap": "12px", "alignItems": "flex-end", "minHeight": "270px"},
        children=[podium_block(place, *items[idx], height) for place, idx, height in order],
    )
 
 
# A dobogó egy oszlopa a felirattal
def podium_block(place: int, name: str, subtitle: str, points: float, color: str, height: int):
    d = PODIUM_DELAY[place]
    return html.Div(style={"flex": "1", "textAlign": "center", "alignSelf": "flex-end"}, children=[
        html.Div(className="podium-text", style={"animationDelay": f"{d + 0.3}s"}, children=[
            html.Div(name, style={"fontWeight": "700", "fontSize": "18px"}),
            html.Div(subtitle, style={"color": MUTED, "fontSize": "13px", "marginBottom": "6px"}),
            html.Div(f"{points:.0f} pont", style={"color": color, "fontWeight": "700", "marginBottom": "8px"}),
        ]),
        # az oszlop nulláról nő a célmagasságig
        html.Div(str(place), className="podium-bar", style={
            "height": f"{height}px", "animationDelay": f"{d}s",
            "background": f"linear-gradient(180deg, {color}, #00000055)",
            "borderRadius": "6px 6px 0 0", "fontSize": "52px", "fontWeight": "900",
            "fontStyle": "italic", "paddingTop": "10px", "overflow": "hidden",
        }),
    ])
 
 
# 5. FŐOLDAL
 
# ---------------------------------------------------------- Földgömb
#A forgatást a böngészőben futó JS végzi (lásd az oldalsablont lejjebb).
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
    rows = [stat_row(label, value, 20) for label, value in stats.items()]
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
def lap_rows_data(rn):
    rows = []
    entries = tel_entries(rn)
    for e in entries:
        rows.append((e["name"], f"leggyorsabb kör · {e['pos']} · {e['lapno']}. kör",
                     e["laptime"], e["color"]))

    # A futam leggyorsabb köre, ha az a pilóta még nincs a listában
    fd_abbr = _get(rn, "fastest_driver")
    fast_time = _get(rn, "fastest_time")
    if to_sec(fast_time) is not None and fd_abbr not in [e["abbr"] for e in entries]:
        res = results[(results["RoundNumber"] == rn) & (results["Abbreviation"] == fd_abbr)]
        if not res.empty:
            r = res.iloc[0]
            color = pick_color(fd_abbr, r["TeamColor"])
            pos = fmt_pos(r["Position"])
        else:
            color, pos = "#6B6B7B", "–"
        try:
            lap_txt = f" · {int(float(_get(rn, 'fastest_lap_no')))}. kör"
        except ValueError:
            lap_txt = ""
        rows.append((NAMES.get(fd_abbr, fd_abbr),
                     f"a futam leggyorsabb köre · {pos}{lap_txt}",
                     fast_time, color))

    ver_color = pick_color("VER", drivers.loc[drivers["Abbreviation"] == "VER", "TeamColor"].iloc[0])
    rows += [
        ("Max Verstappen", "átlagos körideje", _get(rn, "ver_avg"), ver_color),
        ("Mezőny", "átlagos körideje", _get(rn, "avg_all"), "#6B6B7B"),
    ]
    return [(n, sub, t, to_sec(t), c) for n, sub, t, c in rows if to_sec(t) is not None]
 
 
# A sávok felépítése
# Visszaad: a megjelenítendő elemek listája, vagy None, ha nincs adat.
def lap_bars(rn):
    rows = lap_rows_data(rn)
    if not rows:
        return None
 
    # A futam leggyorsabb köre
    fd = NAMES.get(_get(rn, "fastest_driver"), _get(rn, "fastest_driver"))
    fast_lap = _get(rn, "fastest_lap_no")
    fast_time = _get(rn, "fastest_time")
    fast_sec = to_sec(fast_time)
 
    # A skála: a legkisebb és legnagyobb idő köré kis ráhagyással
    secs = [r[3] for r in rows]
    lo, hi = min(secs), max(secs)
    if fast_sec is not None:
        lo = min(lo, fast_sec)
    pad = max((hi - lo) * 0.3, 0.5)
    axis_lo, axis_hi = lo - pad, hi + pad * 1.5
 
    def frac(s):
        return (s - axis_lo) / (axis_hi - axis_lo) * 100
 
    # Rendezett sorrend: leggyorsabb elöl
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
            track.append(html.Div(className="lap-fast", style={"left": f"{frac(fast_sec):.1f}%"}))
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
            style={"display": "flex", "alignItems": "center", "gap": "8px", "fontSize": "13px",
                   "margin": "4px 0 14px"}))
    out.append(html.Div(id="lap-wrap", className="lap-wrap",
                        style={"height": f"{len(rows) * LAP_ROW_H}px"}, children=html_rows))
    return out
 
 
# A "Köridők" szakasz: cím, magyarázat, rendező jelölőnégyzet és a sávok
# (vagy üzenet, ha nincs adat).
def lap_section(rn):
    parts = lap_bars(rn)
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
 
# ---------------------------------------------------------- Időjárás
# idő, hőmérsékletek, nyomás, páratartalom, szél és eső
def weather_section(rn):
    return [section_title("Időjárás"), tile_grid([
        tile("Idő", _get(rn, "condition"), _get(rn, "cloud_cover", "felhőzet: {:.0f}%")),
        tile("Levegő hőmérséklete", _get(rn, "air_temp", "{:.1f}", " °C")),
        tile("Aszfalt hőmérséklete", _get(rn, "track_temp", "{:.1f}", " °C")),
        tile("Légnyomás", _get(rn, "pressure", "{:.0f}", " hPa")),
        tile("Páratartalom", _get(rn, "humidity", "{:.0f}", " %")),
        tile("Szél", _get(rn, "wind_speed", "{:.1f}", " m/s")),
        tile("Eső", _get(rn, "rain_pct", "{:.0f}", " %"), "a futam idejének hány %-ában"),
    ])]
 
 
# ---------------------------------------------------------- Telemetria
# Egy pilóta telemetria-fájljának útja az adott futamhoz.
def tel_path(rn, abbr):
    return P / "telemetry" / f"round_{rn:02d}_{abbr}.csv"
 
 
# Az adott futam telemetriái a befutó sorrendjében
# (rövidítés, név, szín, köridő, körszám, helyezés).
def tel_entries(rn):
    idx = tel_index[tel_index["RoundNumber"] == rn].set_index("Driver")
    res = results[results["RoundNumber"] == rn].sort_values("Position")
    out = []
    for _, r in res.iterrows():
        a = r["Abbreviation"]
        if a in idx.index and tel_path(rn, a).exists():
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
                           "borderRadius": "50%", "background": e["color"], "margin": "0 6px 0 4px"})
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
    entries = [e for e in tel_entries(rn) if e["abbr"] in (selected or [])]
    if not entries:
        return empty_fig("Válassz ki legalább egy pilótát.")
 
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
                x=grid, y=y, name=abbr, legendgroup=abbr,
                showlegend=(i == 1), line={**line, **extra},
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
        height=200 * len(panels) + 80, hovermode="x unified",
        legend=dict(orientation="h", x=0, y=1.06, bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=50, r=20, t=50, b=40))
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
        html.Div("Az első 3 helyezett és Verstappen leggyorsabb köre. Pipáld ki, kiket hasonlítson "
                 "össze; az időkülönbség az első kijelölt pilótához képest értendő.",
                 style={"color": MUTED, "fontSize": "12px", "marginBottom": "8px"}),
        dcc.Checklist(
            id="tel-drivers",
            options=[tel_option(e) for e in entries],
            value=[e["abbr"] for e in entries],
            inputStyle={"accentColor": RED},
            labelStyle={"display": "inline-block", "marginRight": "18px", "color": TEXT},
        ),
        dcc.Graph(id="tel-graph", config={"displayModeBar": False}),
    ]
 
# ---------------------------------------------------------- Futamoldal elrendezés
# A futamoldal kártyája: köridők + időjárás + telemetria
def build_extra(rn: int):
    if summary.empty:
        body = [html.Div("Futtasd előbb a dataset.py-t, hogy elkészüljön a race_summary.csv.",
                         style={"color": MUTED})]
    else:
        body = lap_section(rn) + weather_section(rn) + telemetry_section(rn)
    return html.Div(style=card, children=body)
 
 
# Egy futam teljes oldala: visszagomb, cím, eredmény + bajnoki állás
# dobogó, a részletek kártya, a pontok alakulása vonaldiagramon.
def race_page(rn: int):
    ev = events[events["RoundNumber"] == rn].iloc[0]
    return html.Div(className="page-right", children=[
        html.Button("← Vissza a naptárhoz", id="back-btn", n_clicks=0,
                    style={"background": "none", "border": "none", "padding": 0, "cursor": "pointer",
                           "color": RED, "fontWeight": "700", "textTransform": "uppercase",
                           "fontSize": "13px", "fontFamily": FONT}),
        html.Div(style={"borderLeft": f"8px solid {RED}", "paddingLeft": "16px", "margin": "16px 0 24px"}, children=[
            html.Div(f"{rn}. forduló", style={"color": RED, "fontWeight": "700", "textTransform": "uppercase"}),
            html.H1(ev["EventName"], style={"margin": 0, "fontStyle": "italic", "textTransform": "uppercase"}),
            html.Div(f"{ev['Location']}, {ev['Country']} · {str(ev['EventDate'])[:10]}", style={"color": MUTED}),
        ]),
        html.Div(style={"display": "flex", "flexDirection": "column", "gap": "24px"}, children=[
            html.Div(style={"display": "flex", "gap": "24px", "alignItems": "stretch", "flexWrap": "wrap"}, children=[
                # Futam eredménye
                html.Div(style={**card, "flex": "1", "minWidth": "300px"}, children=[
                    html.H3("Futam eredménye", style={"marginTop": 0, "textTransform": "uppercase"}),
                    race_detail(rn, header=False),
                ]),
                # Bajnoki állás a futam után
                html.Div(style={**card, "flex": "2", "minWidth": "400px"}, children=[
                    html.Div(style=header_row, children=[
                        html.H3(f"Bajnoki állás a(z) {rn}. futam után",
                                style={"margin": 0, "textTransform": "uppercase"}),
                        mode_radio("r-podium-mode"),
                    ]),
                    html.Div(id="r-podium-container", style={"marginTop": "20px"}, children=podium("drivers", rn)),
                ]),
            ]),
            # Köridők, időjárás, telemetria
            build_extra(rn),
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
                    + '.lap-fast { position: absolute; top: -4px; bottom: -4px; width: 3px; margin-left: -1px; background: #E10600; border-radius: 2px; }'
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
                    .replace("__LAP_CSS__", _lap_css()))
 
# Az oldal váza: egy URL-figyelő és egy hely, ahová az aktuális oldal kerül
app.layout = html.Div(style={"background": BG, "color": TEXT, "fontFamily": FONT,
                             "minHeight": "100vh", "padding": "24px 40px"}, children=[
    dcc.Location(id="url", refresh=False),
    html.Div(id="page"),
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
# Az URL alapján kiválasztja az oldalt: "/race/<szám>" a futamoldal, minden más a főoldal.
@app.callback(Output("page", "children"), Input("url", "pathname"))
def route(path):
    if path and path.startswith("/race/"):
        rn = round_from_path(path)
        if rn is not None:
            return race_page(rn)
    return home_layout()
 
 
# ---------------------------------------------------------- Navigáció
# Két külön callback kell, mert egy oldalon mindig csak az egyik bemenet létezik.
 
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
@app.callback(Output("podium-container", "children"), Input("podium-mode", "value"))
def update_podium(mode):
    return podium(mode)
 
 
# ---------------------------------------------------------- Futamoldal callbackek
# Pilóták ki-be pipálása -> a telemetria-diagram újrarajzolása
@app.callback(Output("tel-graph", "figure"),
              Input("tel-drivers", "value"), State("url", "pathname"))
def update_telemetry(selected, path):
    rn = round_from_path(path)
    if rn is None:
        raise PreventUpdate
    return telemetry_figure(rn, selected)
 
 
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
              Input("r-podium-mode", "value"), State("url", "pathname"))
def update_race_podium(mode, path):
    rn = round_from_path(path)
    if rn is None:
        raise PreventUpdate
    return podium(mode, rn)

# Köridők rendezése
app.clientside_callback(
    "function (value) { return (value && value.length) ? 'lap-wrap lap-sorted' : 'lap-wrap'; }",
    Output("lap-wrap", "className"),
    Input("lap-sort", "value"),
)
 
if __name__ == "__main__":
    app.run(debug=True)
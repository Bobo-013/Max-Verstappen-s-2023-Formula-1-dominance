import time
from pathlib import Path
 
import pandas as pd
import plotly.graph_objects as go
import numpy as np
from plotly.subplots import make_subplots
from dash import Dash, Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate
from functools import lru_cache
import math
 
BASE = Path(__file__).resolve().parent
P = BASE / "data" / "processed"
drivers = pd.read_csv(P / "drivers.csv", dtype={"TeamColor":str})
teams = pd.read_csv(P / "teams.csv", dtype={"TeamColor":str})
d_cum = pd.read_csv(P / "driver_cumulative_points.csv", index_col=0)
t_cum = pd.read_csv(P / "team_cumulative_points.csv", index_col=0)
events = pd.read_csv(P / "events.csv")
stats = pd.read_csv(P / "verstappen_stats.csv", index_col=0)["value"]
 
round_names = events.set_index("RoundNumber")["EventName"].to_dict()
 
results = pd.read_csv(
    BASE / "data" / "Results.csv",
    usecols=["Abbreviation", "FullName", "TeamName", "TeamColor",
             "Position", "GridPosition", "Points", "RoundNumber"], dtype={"TeamColor":str},
)

NAMES = results.drop_duplicates("Abbreviation").set_index("Abbreviation")["FullName"].to_dict()

_ti = P / "telemetry_index.csv"
tel_index = (pd.read_csv(_ti).dropna(subset=["LapTime"]) if _ti.exists()
             else pd.DataFrame(columns=["RoundNumber", "Driver", "LapTime", "LapNumber"]))

RED = "#E10600"
BG = "#15151E"
PANEL = "#1F1F2B"
TEXT = "#F2F2F2"
MUTED = "#9A9AAA"
FONT = "'Titillium Web', 'Segoe UI', Arial, sans-serif"
 
# Földgömb forgatása
START_LON = 20      # kezdő hosszúsági fok
START_LAT = 25      # dőlésszög
STEP_DEG = 0.5        # ennyi fokot fordul egy tick alatt
INTERVAL_MS = 50    # tick gyakorisága (ms)
 
# Oldalváltás animációi (másodperc)
PAGE_OUT_S = 0.7    # a régi oldal kicsúszása
PAGE_IN_S = 0.9     # az új oldal becsúszása

#Telemetria
TEL_COLS_USED = ["SessionTime", "LapNumber", "LapTimeInLap", "Speed",
                 "Throttle", "Brake", "nGear"]
MAX_PTS = 15000 
 
def _shade(hex_color, factor):
    """factor > 0: világosítás a fehér felé, factor < 0: sötétítés a fekete felé."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    target = 255 if factor > 0 else 0
    f = abs(factor)
    r, g, b = (round(c + (target - c) * f) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def _luma(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


# Csapaton belüli sorrend a szezon végi pontok szerint (a drivers.csv már így van rendezve)
_team_rank = {}
for _, grp in drivers.groupby("TeamColor", sort=False):
    for i, a in enumerate(grp["Abbreviation"]):
        _team_rank[a] = i


def _hex(team_color):
    h = str(team_color).strip().lstrip("#")
    if h.endswith(".0"):
        h = h[:-2]
    return "#" + h.zfill(6)


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
 
 
# ---------------------------------------------------------------- Vonaldiagram
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
 
 
# ------------------------------------------------------------------- Dobogó
# Mikor induljon az animáció az egyes helyezéseknél (másodperc): 3. -> 2. -> 1.
PODIUM_DELAY = {3: 0.0, 2: 0.9, 1: 1.8}
 
 
def podium_block(place: int, name: str, subtitle: str, points: float, color: str, height: int):
    d = PODIUM_DELAY[place]
    return html.Div(style={"flex": "1", "textAlign": "center", "alignSelf": "flex-end"}, children=[
        # felirat: az oszlop növekedése közben tűnik elő
        html.Div(className="podium-text", style={"animationDelay": f"{d + 0.3}s"}, children=[
            html.Div(name, style={"fontWeight": "700", "fontSize": "18px"}),
            html.Div(subtitle, style={"color": MUTED, "fontSize": "13px", "marginBottom": "6px"}),
            html.Div(f"{points:.0f} pont", style={"color": color, "fontWeight": "700", "marginBottom": "8px"}),
        ]),
        # oszlop: nulláról nő a célmagasságig
        html.Div(str(place), className="podium-bar", style={
            "height": f"{height}px", "animationDelay": f"{d}s",
            "background": f"linear-gradient(180deg, {color}, #00000055)",
            "borderRadius": "6px 6px 0 0", "fontSize": "52px", "fontWeight": "900",
            "fontStyle": "italic", "paddingTop": "10px", "overflow": "hidden",
        }),
    ])
 
 
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
 
    order = [(2, 1, 110), (1, 0, 160), (3, 2, 80)]
    return html.Div(
        style={"display": "flex", "gap": "12px", "alignItems": "flex-end", "minHeight": "270px"},
        children=[podium_block(place, *items[idx], height) for place, idx, height in order],
    )
 
 
# ---------------------------------------------------------------- Földgömb
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
 
 
# ---------------------------------------------------------------- Futam adatok
def fmt_pos(value):
    return f"P{int(value)}" if pd.notna(value) and value > 0 else "–"
 
 
_sf = P / "race_summary.csv"
summary = pd.read_csv(_sf).set_index("RoundNumber") if _sf.exists() else pd.DataFrame()
 
 
def _get(rn, col, fmt="{}", suffix=""):
    try:
        v = summary.loc[rn, col]
    except KeyError:
        return "–"
    if pd.isna(v):
        return "–"
    return fmt.format(v) + suffix
 
 
def tile(label, value, sub=None, color=TEXT):
    return html.Div(style={"background": BG, "padding": "12px 14px", "borderRadius": "6px"}, children=[
        html.Div(label, style={"color": MUTED, "fontSize": "11px", "textTransform": "uppercase",
                               "letterSpacing": "1px"}),
        html.Div(value, style={"fontSize": "24px", "fontWeight": "900", "fontStyle": "italic", "color": color}),
        html.Div(sub or "", style={"color": MUTED, "fontSize": "12px", "minHeight": "16px"}),
    ])
 
 
def tile_grid(children):
    return html.Div(children=children, style={
        "display": "grid", "gridTemplateColumns": "repeat(auto-fit, minmax(170px, 1fr))", "gap": "10px"})
 
 
def section_title(text):
    return html.H4(text, style={"margin": "20px 0 10px", "textTransform": "uppercase", "color": RED,
                                "fontSize": "13px", "letterSpacing": "1px"})
 
 
def stat_row(label, value, size=18):
    return html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "baseline",
                           "padding": "8px 0", "borderBottom": "1px solid #2E2E3E", "gap": "10px"}, children=[
        html.Div(str(label), style={"color": MUTED, "fontSize": "13px"}),
        html.Div(str(value), style={"fontSize": f"{size}px", "fontWeight": "900", "fontStyle": "italic"}),
    ])
 
 
def season_stats_children():
    rows = [stat_row(label, value, 20) for label, value in stats.items()]
    return [
        html.H3("Verstappen 2023", style={"marginTop": 0, "textTransform": "uppercase"}),
        *rows,
        html.Div("Vidd az egeret egy futam fölé a részletekért.",
                 style={"color": MUTED, "fontSize": "12px", "marginTop": "12px"}),
    ]
 
 
def side_panel():
    return html.Div(id="side-panel",
                    style={"background": PANEL, "padding": "20px", "borderRadius": "8px"},
                    children=season_stats_children())

#------------------------Kör idők
def to_sec(t):
    """'1:23.456' -> 83.456 (másodperc)"""
    if not isinstance(t, str) or ":" not in t:
        return None
    m, s = t.split(":")
    return int(m) * 60 + float(s)

def lap_figure(rn):
    rows = []
    for e in tel_entries(rn):
        rows.append((f"{e['name']}<br>leggyorsabb köre", e["laptime"], e["color"],
                     f"{e['pos']} · {e['lapno']}. kör"))

    rows += [
        ("Max Verstappen<br>átlagos köre", _get(rn, "ver_avg"), pick_color("VER", drivers.loc[drivers["Abbreviation"] == "VER", "TeamColor"].iloc[0]), "107%-on belüli körök"),
        ("Mezőny<br>átlagos köre", _get(rn, "avg_all"), "#6B6B7B", "107%-on belüli körök"),
    ]
    rows = [(n, t, to_sec(t), c, sub) for n, t, c, sub in rows if to_sec(t) is not None]
    if not rows:
        return None

    # a futam leggyorsabb köre: vízszintes vonal
    fd = NAMES.get(_get(rn, "fastest_driver"), _get(rn, "fastest_driver"))
    fast_lap = _get(rn, "fastest_lap_no")
    fast_time = _get(rn, "fastest_time")
    fast_sec = to_sec(fast_time)

    secs = [r[2] for r in rows]
    lo, hi = min(secs), max(secs)
    if fast_sec is not None:
        lo = min(lo, fast_sec)
    pad = max((hi - lo) * 0.3, 0.5)

    fig = go.Figure(go.Bar(
        x=[r[0] for r in rows], y=secs,
        marker=dict(color=[r[3] for r in rows]),
        text=[r[1] for r in rows], textposition="outside", cliponaxis=False,
        textfont=dict(size=15, color=TEXT),
        customdata=[[r[1], r[4]] for r in rows],
        hovertemplate="<b>%{x}</b><br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>",
    ))

    if fast_sec is not None:
        who = f" ({fd}" + (f" · {int(fast_lap)}. kör" if fast_lap is not None else "") + ")" if fd else ""
        fig.add_hline(
            y=fast_sec, line=dict(color=RED, width=3, dash="solid"),
            annotation_text=f"<b>Futam leggyorsabb köre:</b><br>{fast_time}{who}",
            annotation_position="top right",
            annotation_font=dict(color="#F2F2F2", size=13),
        )

    fig.update_yaxes(range=[lo - pad, hi + pad * 1.5], title_text="Köridő (s)",
                     gridcolor="#2E2E3E")
    fig.update_xaxes(showgrid=False)
    fig.update_layout(
        paper_bgcolor=PANEL, plot_bgcolor=PANEL, font=dict(color=TEXT, family=FONT),
        height=360, margin=dict(l=50, r=20, t=30, b=40), bargap=0.45,
        hoverlabel=dict(font_size=14, font_family=FONT))
    return fig


def lap_section(rn):
    fig = lap_figure(rn)
    if fig is None:
        return [section_title("Köridők"),
                html.Div("Nincs köridő ehhez a futamhoz.", style={"color": MUTED})]
    return [
        section_title("Köridők"),
        html.Div("A függőleges tengely nem nulláról indul, hogy a másodpercek közti "
                 "különbségek is látszódjanak.",
                 style={"color": MUTED, "fontSize": "12px", "marginBottom": "4px"}),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
    ]
 
 
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


#---------------------------------------------Telemetria
def tel_path(rn, abbr):
    return P / "telemetry" / f"round_{rn:02d}_{abbr}.csv"


def tel_entries(rn):
    """Az adott futam elérhető telemetriái a befutó sorrendjében."""
    idx = tel_index[tel_index["RoundNumber"] == rn].set_index("Driver")
    res = results[results["RoundNumber"] == rn].sort_values("Position")
    out = []
    for _, r in res.iterrows():
        a = r["Abbreviation"]
        if a in idx.index and tel_path(rn, a).exists():
            out.append({
                "abbr": a,
                "name": NAMES.get(a,a),
                "color": pick_color(a, r["TeamColor"]),
                "laptime": idx.loc[a, "LapTime"],
                "lapno": int(idx.loc[a, "LapNumber"]),
                "pos": fmt_pos(r["Position"]),
            })
    return out


def tel_option(e):
    dot = html.Span(style={"display": "inline-block", "width": "10px", "height": "10px",
                           "borderRadius": "50%", "background": e["color"], "margin": "0 6px 0 4px"})
    return {"label": html.Span([dot, f"{e['abbr']} ({e['pos']}) · {e['lapno']} kör"]),
            "value": e["abbr"]}


@lru_cache(maxsize=48)
def load_tel(rn, abbr):
    """(telemetria DataFrame futam-x-szel, körkezdési idők) – egyszer olvassa be, utána cache."""
    d = pd.read_csv(tel_path(rn, abbr), usecols=TEL_COLS_USED)
    d = d.dropna(subset=["LapNumber", "LapTimeInLap"]).sort_values(["LapNumber", "LapTimeInLap"])
    d["LapNumber"] = d["LapNumber"].astype(int)

    # körkezdési idő (session idő) – az időkülönbség panelhez
    starts = (d["SessionTime"] - d["LapTimeInLap"]).groupby(d["LapNumber"]).first()

    # futam-előrehaladás körökben: 0 … körök száma
    dur = d.groupby("LapNumber")["LapTimeInLap"].transform("max").replace(0, np.nan)
    d["x"] = d["LapNumber"] - 1 + (d["LapTimeInLap"] / dur).fillna(0)

    d["Brake"] = d["Brake"].astype(float).clip(0, 1) * 100

    step = max(1, math.ceil(len(d) / MAX_PTS))
    return d.iloc[::step].reset_index(drop=True), starts


def empty_fig(text):
    fig = go.Figure()
    fig.update_layout(paper_bgcolor=PANEL, plot_bgcolor=PANEL, height=200,
                      font=dict(color=TEXT, family=FONT),
                      xaxis=dict(visible=False), yaxis=dict(visible=False),
                      annotations=[dict(text=text, showarrow=False, font=dict(color=MUTED))])
    return fig


def telemetry_figure(rn, selected):
    entries = [e for e in tel_entries(rn) if e["abbr"] in (selected or [])]
    if not entries:
        fig = go.Figure()
        fig.update_layout(paper_bgcolor=PANEL, plot_bgcolor=PANEL, height=200,
                          font=dict(color=TEXT, family=FONT),
                          xaxis=dict(visible=False), yaxis=dict(visible=False),
                          annotations=[dict(text="Válassz ki legalább egy pilótát.",
                                            showarrow=False, font=dict(color=MUTED))])
        return fig

    data = {e["abbr"]: pd.read_csv(tel_path(rn, e["abbr"])) for e in entries}
    end = min(d["Distance"].max() for d in data.values())
    grid = np.arange(0, end, 1)

    def on_grid(d, col):
        return np.interp(grid, d["Distance"], d[col])

    ref = entries[0]["abbr"]
    ref_time = on_grid(data[ref], "Time")

    panels = [(f"Időkülönbség (s) – {ref}-hez képest (+ = lassabb)", 0.22),
              ("Sebesség (km/h)", 0.32), ("Gáz (%)", 0.16),
              ("Fék", 0.12), ("Sebességfokozat", 0.18)]

    fig = make_subplots(rows=len(panels), cols=1, shared_xaxes=True, vertical_spacing=0.035,
                        row_heights=[h for _, h in panels],
                        subplot_titles=[t for t, _ in panels])

    for e in entries:
        abbr = e["abbr"]
        d = data[abbr]
        dash = "dot" if _team_rank.get(abbr, 0) > 0 else "solid"   # csapattársak megkülönböztetése
        line = dict(color=e["color"], width=1.5, dash=dash)

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


def telemetry_section(rn):
    entries = tel_entries(rn)
    title = section_title("Telemetria – a teljes futam")
    if not entries:
        return [title, html.Div("Nincs telemetria ehhez a futamhoz.", style={"color": MUTED})]
    return [
        title,
        html.Div("Az első 3 helyezett és Verstappen az egész futamon. Pipáld ki, kiket hasonlítson "
                 "össze; az időkülönbség az első kijelölt pilótához képest értendő. "
                 "Az alsó csúszkával vagy a grafikonon húzva egy-egy kör is megnézhető.",
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
 
 
def build_extra(rn: int):
    """A futam oldal kártyája: köridők, időjárás, telemetria."""
    if summary.empty:
        body = [html.Div("Futtasd előbb a dataset.py-t, hogy elkészüljön a race_summary.csv.",
                         style={"color": MUTED})]
    else:
        body = lap_section(rn) + weather_section(rn) + telemetry_section(rn)
    return html.Div(style={"background": PANEL, "padding": "20px", "borderRadius": "8px"}, children=body)
 
 
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
 
 
# --------------------------------------------------------------------- APP LAYOUT
app = Dash(__name__, suppress_callback_exceptions=True)
app.title = "Verstappen 2023"
 
# A forgatást végző JS az oldal sablonjába kerül, így nincs szükség külön fájlra
app.index_string = """<!DOCTYPE html>
<html>
<head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <script>
        (function () {
            // Dobogó-animáció CSS (a forgató scripttel együtt kerül az oldalba)
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
                    + 'html, body { overflow-x: hidden; }';
            var st = document.createElement('style');
            st.id = 'podium-css';
            st.textContent = css;
            document.head.appendChild(st);
        })();
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
                syncButton();
                var el = document.getElementById('globe');
                var gd = el ? el.querySelector('.js-plotly-plot') : null;
                // Földgömb pontjára kattintás: a főoldal balra csúszik ki
                if (gd && typeof gd.on === 'function' && !gd._exitBound) {
                    gd._exitBound = true;
                    gd.on('plotly_click', function () { exitPage('left'); });
                }
                if (paused) return;
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
</html>""".replace("__START_LON__", str(START_LON)).replace("__STEP_DEG__", str(STEP_DEG)).replace("__INTERVAL_MS__", str(INTERVAL_MS)) \
    .replace("__PAGE_IN_S__", str(PAGE_IN_S)).replace("__PAGE_OUT_S__", str(PAGE_OUT_S))
 
card = {"background": PANEL, "padding": "20px", "borderRadius": "8px"}
 
 
def mode_radio(component_id: str):
    return dcc.RadioItems(
        id=component_id,
        options=[{"label": " Pilóták", "value": "drivers"},
                 {"label": " Konstruktőrök", "value": "teams"}],
        value="drivers", inline=True,
        inputStyle={"marginLeft": "16px", "accentColor": RED},
        labelStyle={"color": TEXT},
    )
 
 
header_row = {"display": "flex", "justifyContent": "space-between", "alignItems": "center"}
 
button_style = {"background": "#33334A", "color": TEXT, "border": "none", "padding": "8px 14px",
                "borderRadius": "6px", "cursor": "pointer", "fontFamily": FONT, "marginTop": "8px"}
 
 
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
            html.Div(style={"flex": "1", "minWidth": "260px"}, children=[side_panel()]),
        ]),
    ])
 
 
# ----------------------------------------------------------------- Futam oldal
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
                html.Div(style={**card, "flex": "1", "minWidth": "300px"}, children=[
                    html.H3("Futam eredménye", style={"marginTop": 0, "textTransform": "uppercase"}),
                    race_detail(rn, header=False),
                ]),
                html.Div(style={**card, "flex": "2", "minWidth": "400px"}, children=[
                    html.Div(style=header_row, children=[
                        html.H3(f"Bajnoki állás a(z) {rn}. futam után",
                                style={"margin": 0, "textTransform": "uppercase"}),
                        mode_radio("r-podium-mode"),
                    ]),
                    html.Div(id="r-podium-container", style={"marginTop": "20px"}, children=podium("drivers", rn)),
                ]),
            ]),
            build_extra(rn),
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
 
 
app.layout = html.Div(style={"background": BG, "color": TEXT, "fontFamily": FONT,
                             "minHeight": "100vh", "padding": "24px 40px"}, children=[
    dcc.Location(id="url", refresh=False),
    html.Div(id="page"),
])
 
 
def round_from_path(path):
    try:
        rn = int(path.strip("/").split("/")[1])
        return rn if rn in round_names else None
    except (AttributeError, IndexError, ValueError):
        return None
 
 
# ------------------------------------------------------------------ Callbackek
@app.callback(Output("page", "children"), Input("url", "pathname"))
def route(path):
    if path and path.startswith("/race/"):
        rn = round_from_path(path)
        if rn is not None:
            return race_page(rn)
    return home_layout()
 
 
# Navigáció. A kis késleltetés alatt játszódik le a régi oldal kicsúszása (JS).
# Két külön callback, mert egy oldalon mindig csak az egyik bemenet létezik.
@app.callback(Output("url", "pathname", allow_duplicate=True),
              Input("globe", "clickData"), prevent_initial_call=True)
def go_to_race(click):
    if not click:
        raise PreventUpdate
    time.sleep(PAGE_OUT_S)
    return f"/race/{int(click['points'][0]['customdata'][0])}"
 
 
@app.callback(Output("url", "pathname", allow_duplicate=True),
              Input("back-btn", "n_clicks"), prevent_initial_call=True)
def go_home(n_clicks):
    if not n_clicks:
        raise PreventUpdate
    time.sleep(PAGE_OUT_S)
    return "/"
 
 
# Földgömb hover -> oldalsó panel
@app.callback(Output("side-panel", "children"), Input("globe", "hoverData"))
def hover_side(hover):
    if not hover:
        return season_stats_children()
    return hover_panel_children(int(hover["points"][0]["customdata"][0]))
 
 
# Futam oldal
@app.callback(Output("tel-graph", "figure"),
              Input("tel-drivers", "value"), State("url", "pathname"))
def update_telemetry(selected, path):
    rn = round_from_path(path)
    if rn is None:
        raise PreventUpdate
    return telemetry_figure(rn, selected)
 
 
@app.callback(Output("r-line-chart", "figure"),
              Input("r-line-mode", "value"), State("url", "pathname"))
def update_race_chart(mode, path):
    rn = round_from_path(path)
    if rn is None:
        raise PreventUpdate
    return build_line_chart(mode, rn)

@app.callback(Output("r-podium-container", "children"),
              Input("r-podium-mode", "value"), State("url", "pathname"))
def update_race_podium(mode, path):
    rn = round_from_path(path)
    if rn is None:
        raise PreventUpdate
    return podium(mode, rn)
 
# Főoldal
@app.callback(Output("line-chart", "figure"), Input("mode", "value"))
def update_chart(mode):
    return build_line_chart(mode)
 
 
@app.callback(Output("podium-container", "children"), Input("podium-mode", "value"))
def update_podium(mode):
    return podium(mode)
 
 
if __name__ == "__main__":
    app.run(debug=True)
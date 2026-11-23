import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from components import _best_txt
from config import LAP_ROW_H, MUTED, PANEL, RED, FONT, TEXT, TYRE_COLORS, TYRE_NAMES
from data import LAPS, NAMES, SESS, drivers
from helpers import (_get, _rgba, _team_rank, fmt_lap, fmt_pos, pick_color, section_title,
                     stat_row, to_sec)
from race_telemetry import tel_entries


# 8. FUTAMOLDAL
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

# ---------------------------------------------------------- Köridők eloszlása
# Az első 3 helyezett, Verstappen, a leggyorsabb kör pilótája és a mezőny pontos köreinek eloszlása.
BOX_MAX = 1.07   # a pilóta mediánjának 107%-ánál lassabb köröket kihagyjuk
FIELD_COLOR = "#6B6B7B"

def lap_box_section(rn, s="R"):
    laps = LAPS.get(s)
    if laps is None:
        return []
    L = laps[laps["RoundNumber"] == rn]
    if L.empty:
        return []

    res = SESS[s]["results"]
    res = res[res["RoundNumber"] == rn].sort_values("Position")
    info = res.set_index("Abbreviation")

    pick = res.head(3)["Abbreviation"].tolist()
    if "VER" not in pick:
        pick.append("VER")

    # A futam leggyorsabb körét futó pilóta
    fast_abbr = _get(rn, "fastest_driver", s=s)
    if fast_abbr not in pick:
        pick.append(fast_abbr)

    # Pontos körök, pilótánként a medián 107%-ánál lassabbak nélkül
    acc = L[L["LapSec"].notna()]
    if "IsAccurate" in acc.columns:
        acc = acc[acc["IsAccurate"].fillna(False).astype(bool)]
    n_before = len(acc)
    med = acc.groupby("Driver")["LapSec"].transform("median")
    acc = acc[acc["LapSec"] <= med * BOX_MAX]
    skipped = n_before - len(acc)

    fig = go.Figure()
    all_y = []
    for abbr in pick:
        d = acc[acc["Driver"] == abbr]
        if len(d) < 3 or abbr not in info.index:
            continue

        color = pick_color(abbr, info.loc[abbr, "TeamColor"])
        label = f"{NAMES.get(abbr, abbr)} ({fmt_pos(info.loc[abbr, 'Position'])})"
        if abbr == fast_abbr:
            label += "<br>leggyorsabb kör"
        comp = (d["Compound"].fillna("UNKNOWN").astype(str).str.upper()
                if "Compound" in d.columns else pd.Series("UNKNOWN", index=d.index))
        comp = comp.where(comp.isin(TYRE_COLORS), "UNKNOWN")
        hovertext = [f"{int(n)}. kör · {TYRE_NAMES[c]} · {fmt_lap(v)}"
                     for n, c, v in zip(d["LapNumber"], comp, d["LapSec"])]
        all_y += d["LapSec"].tolist()

        fig.add_trace(go.Box(
            y=d["LapSec"], name=label, boxpoints="all", jitter=0.5, pointpos=0,
            boxmean=True, line=dict(color=color, width=2),
            fillcolor=_rgba(color, 0.25),
            marker=dict(color=color, size=5, opacity=0.65),
            hovertext=hovertext,
        ))

    if not all_y:
        return []

    lo, hi = min(all_y), max(all_y)
    pad = max((hi - lo) * 0.08, 0.3)
    y0, y1 = lo - pad, hi + pad

    # Másodperc alapú lépésköz, a tartományhoz igazítva
    span = y1 - y0
    step = 0.5 if span <= 4 else 1 if span <= 8 else 2 if span <= 16 else 5
    first = int(y0 // step * step)
    ticks = [first + i * step for i in range(int(span // step) + 3)]
    ticks = [t for t in ticks if y0 <= t <= y1]

    def tick_txt(t):
        t = round(t, 2)
        return f"{int(t // 60)}:{t % 60:04.1f}"

    fig.update_yaxes(range=[y0, y1], tickvals=ticks, ticktext=[tick_txt(t) for t in ticks],
                     gridcolor="#2E2E3E", zeroline=False, hoverformat=".3f",
                     title_text="Köridő", fixedrange=True)
    fig.update_xaxes(showgrid=False, fixedrange=True)
    fig.update_layout(
        paper_bgcolor=PANEL, plot_bgcolor=PANEL, font=dict(color=TEXT, family=FONT),
        height=460, margin=dict(l=70, r=20, t=20, b=40), showlegend=False,
        hoverlabel=dict(bgcolor=PANEL, font=dict(family=FONT, color=TEXT)))

    note = ("Az első 3 helyezett és Verstappen sebességének megoszlása a futam alatt.")
    return [
        section_title("Köridők eloszlása"),
        html.Div(note, style={"color": MUTED, "fontSize": "12px"}),
        dcc.Graph(figure=fig, config={"displayModeBar": False}),
    ]

# Q1 · Q2 · Q3 idők vonaldiagramon, pilótánként egy vonal.
def quali_line_fig(sel):
    stages = ["Q1", "Q2", "Q3"]
    fig = go.Figure()
    all_y = []
    for _, r in sel.iterrows():
        ys = [to_sec(r[k]) if k in r.index else None for k in stages]
        if all(v is None for v in ys):
            continue
        all_y += [v for v in ys if v is not None]
        color = pick_color(r["Abbreviation"], r["TeamColor"])
        dash = "dot" if _team_rank.get(r["Abbreviation"], 0) > 0 else "solid"
        fig.add_trace(go.Scatter(
            x=stages, y=ys, mode="lines+markers", name=r["FullName"], connectgaps=False,
            line=dict(color=color, width=3, dash=dash), marker=dict(size=9, color=color),
            customdata=[fmt_lap(v) for v in ys],
            hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{customdata}<extra></extra>"))
    if not all_y:
        return None

    lo, hi = min(all_y), max(all_y)
    pad = max((hi - lo) * 0.1, 0.3)
    y0, y1 = lo - pad, hi + pad
    span = y1 - y0
    step = 0.5 if span <= 4 else 1 if span <= 8 else 2 if span <= 16 else 5
    first = int(y0 // step * step)
    ticks = [first + i * step for i in range(int(span // step) + 3)]
    ticks = [t for t in ticks if y0 <= t <= y1]

    def tick_txt(t):
        t = round(t, 2)
        return f"{int(t // 60)}:{t % 60:04.1f}"

    fig.update_yaxes(range=[y0, y1], tickvals=ticks, ticktext=[tick_txt(t) for t in ticks],
                     gridcolor="#2E2E3E", zeroline=False, title_text="Idő", fixedrange=True)
    fig.update_xaxes(gridcolor="#2E2E3E", fixedrange=True)
    fig.update_layout(
        paper_bgcolor=PANEL, plot_bgcolor=PANEL, font=dict(color=TEXT, family=FONT),
        height=420, margin=dict(l=70, r=20, t=20, b=40), hovermode="closest",
        hoverlabel=dict(bgcolor=PANEL, font=dict(family=FONT, color=TEXT)),
        legend=dict(orientation="h", x=0, xanchor="left", y=1.12, yanchor="bottom",
                    bgcolor="rgba(0,0,0,0)"))
    return fig

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
    fig = quali_line_fig(sel)
    return [
        title,
        html.Div(f"Leggjobb idő: {_best_txt(pole)} ({pole['FullName']})",
                 style={"fontSize": "13px", "color": MUTED, "margin": "4px 0 14px"}),
        html.Div(className="lap-wrap", style={"height": f"{len(bars) * LAP_ROW_H}px"}, children=bars),
        *([section_title("Időmérő idők alakulása Q1-, Q2-, Q3-ban"),
           html.Div("Az első 3 és Verstappen Q1, Q2 és Q3 ideje. Aki nem jutott tovább, annál a vonal megszakad.",
                    style={"color": MUTED, "fontSize": "12px"}),
           dcc.Graph(figure=fig, config={"displayModeBar": False})] if fig is not None else []),
    ]
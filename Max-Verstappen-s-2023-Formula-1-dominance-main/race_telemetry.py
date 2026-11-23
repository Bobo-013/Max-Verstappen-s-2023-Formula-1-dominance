import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
from plotly.subplots import make_subplots

from config import FONT, MUTED, PANEL, TEXT
from data import NAMES, P, SESS
from helpers import _team_rank, fmt_pos, pick_color, section_title


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
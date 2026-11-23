import pandas as pd
from dash import dcc, html

from config import BG, MUTED, RED, TEXT
from data import SESS, summary, wx_icon
from helpers import _get, section_title


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
    value = _get(rn, col, "{:.0f}" if key != "condition" else "{}", unit, s=s)
    kids = [html.Div(label, style={"fontSize": "12px", "color": MUTED})]
    icon = wx_icon(value) if key == "condition" else ""
    if icon:
        # ikon szöveg nélkül, fix méretű dobozban
        kids.append(html.Img(src=icon, title=value, style={
            "height": "64px", "width": "64px", "objectFit": "contain",
            "display": "block", "margin": "8px auto 0"}))
    else:
        kids.append(html.Div(value, style={"fontSize": "24px", "color": TEXT,
                                           "padding": "8px", "fontWeight": "bold"}))
    return html.Div(
        kids, id={"type": "wx-card", "key": key}, n_clicks=0,
        style={"cursor": "pointer", "borderRadius": "8px", "background": BG,
               "boxSizing": "border-box", "width": "190px", "height": "140px",
               "display": "flex", "flexDirection": "column",
               "alignItems": "center", "justifyContent": "center", "textAlign": "center",
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
        html.Div([wx_card(k, rn, [], s) for k in CRITERIA], id="wx-cards",
                 style={"display": "flex", "flexWrap": "wrap", "gap": "16px"}),
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
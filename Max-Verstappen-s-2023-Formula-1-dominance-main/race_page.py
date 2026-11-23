from dash import dcc, html

from components import build_line_chart, race_detail, session_podium, session_tabs
from config import FONT, MUTED, RED, card, header_row
from data import SESS, round_names
from helpers import mode_radio
from race_laps import lap_box_section, lap_section, quali_section
from race_strategy import tyre_section
from race_telemetry import telemetry_section
from race_weather import weather_section


# ---------------------------------------------------------- Futamoldal elrendezés
# A futamoldal kártyája: köridők + időjárás + telemetria
def build_extra(rn: int, s: str = "R"):
    if s == "Q":
        return html.Div(style=card, children=quali_section(rn))
    if SESS[s]["summary"].empty:
        return html.Div(style=card, children=[
            html.Div("Futtasd előbb a dataset.py-t.", style={"color": MUTED})])
    cards = [
        html.Div(style=card, children=lap_section(rn, s) + lap_box_section(rn, s)),
        html.Div(style=card, children=weather_section(rn, s)),
    ]
    if s == "R":
        cards.append(html.Div(style=card, children=telemetry_section(rn)))
    return html.Div(style={"display": "flex", "flexDirection": "column", "gap": "24px"},
                    children=cards)

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
            # Köridők, időjárás, telemetria, stratégia
            build_extra(rn, s),
            tyre_section(rn, s),
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
import plotly.graph_objects as go
from dash import dcc, html

from components import podium, race_detail
from config import (BG, FONT, MUTED, PANEL, RED, START_LAT, START_LON, TEXT,
                    card, header_row)
from data import LABELS, events, stats, wx_icon
from helpers import _get, mode_radio, stat_row


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
 
 
# Az "Időjárás" sor: ikonnal, ha van hozzá ikon, különben szöveggel
def _weather_row(cond):
    icon = wx_icon(cond)
    if not icon:
        return stat_row("Időjárás", cond, 22)
    return html.Div(style={"display": "flex", "justifyContent": "space-between", "alignItems": "center",
                           "padding": "8px 0", "borderBottom": "1px solid #2E2E3E", "gap": "10px"}, children=[
        html.Div("Időjárás", style={"color": MUTED, "fontSize": "13px"}),
        html.Img(src=icon, title=cond, style={"height": "40px", "width": "40px", "objectFit": "contain"}),
    ])


# Az oldalsáv tartalma, amikor a földgömb egy futama fölött áll az egér:
# eredménykártya + Verstappen leggyorsabb köre, időjárás, hőmérséklet.
def hover_panel_children(rn: int):
    track = _get(rn, "track_temp", "{:.0f}")
    air = _get(rn, "air_temp", "{:.0f}")
    return [
        race_detail(rn),
        html.Div(style={"marginTop": "10px"}, children=[
            stat_row("Verstappen leggyorsabb köre", _get(rn, "ver_best"), 22),
            _weather_row(_get(rn, "condition")),
            stat_row("Aszfalt / levegő", f"{track} / {air} °C", 22),
        ]),
        html.Div("Kattints a futamra a részletes oldalért →",
                 style={"color": MUTED, "fontSize": "12px", "marginTop": "12px"}),
    ]
 
# ---------------------------------------------------------- Főoldal elrendezés
# Főoldali dobogók egymás mellett: pilóták | konstruktőrök
def home_podiums():
    def col(title, mode):
        return html.Div(children=[
            html.Div(title, style={"color": MUTED, "fontSize": "12px", "textTransform": "uppercase",
                                   "letterSpacing": "1px", "textAlign": "center", "marginBottom": "8px"}),
            podium(mode),
        ])
    return html.Div(style={"display": "grid", "gridTemplateColumns": "1fr 1fr", "gap": "32px"},
                    children=[col("Pilóták", "drivers"), col("Konstruktőrök", "teams")])


# Összegző gomb
def summary_button():
    return dcc.Link("Szezon összegzése →", href="/summary", style={
        "display": "block", "marginTop": "48px", "padding": "26px 20px", "textAlign": "center",
        "background": RED, "color": "#FFFFFF", "borderRadius": "8px", "textDecoration": "none",
        "fontSize": "22px", "fontWeight": "900", "fontStyle": "italic",
        "textTransform": "uppercase", "letterSpacing": "1px",
        "boxShadow": "0 6px 18px rgba(225,6,0,.35)"})


def home_layout():
    return html.Div(className="page-left", children=[
        html.Div(style={"borderLeft": f"8px solid {RED}", "paddingLeft": "16px", "marginBottom": "24px"}, children=[
            html.H1("Max Verstappen 2023-as Forma 1-es dominanciája",
                    style={"margin": 0, "fontStyle": "italic", "textTransform": "uppercase"}),
            html.Div("avagy egy rekorddöntő szezon statisztikája", style={"color": MUTED}),
        ]),
        html.Div(style={"display": "flex", "flexDirection": "column", "gap": "24px"}, children=[
            # Felső sor: földgömb + oldalsáv a gombbal
            html.Div(style={"display": "flex", "gap": "24px", "alignItems": "flex-start"}, children=[
                html.Div(style={**card, "flex": "3"}, children=[
                    html.H3("A 2023-as naptár", style={"marginTop": 0, "textTransform": "uppercase"}),
                    html.Div("Vidd az egeret egy futam fölé és kattints a részletes adatokért.",
                             style={"color": MUTED, "fontSize": "13px", "marginBottom": "8px"}),
                    dcc.Graph(id="globe", figure=build_globe(), config={"displayModeBar": False}),
                ]),
                html.Div(style={"flex": "1", "minWidth": "260px"}, children=[
                    side_panel(),
                    summary_button(),
                ]),
            ]),
            # Dobogók egymás mellett, teljes szélességben
            html.Div(style=card, children=[
                html.H3("Végeredmény", style={"marginTop": 0, "textTransform": "uppercase"}),
                html.Div(style={"marginTop": "20px"}, children=home_podiums()),
            ]),
            # Összetett, teljes szélességben
            html.Div(style=card, children=[
                html.Div(style=header_row, children=[
                    html.H3("Összetett bajnokság alakulása", style={"margin": 0, "textTransform": "uppercase"}),
                    mode_radio("mode"),
                ]),
                dcc.Graph(id="line-chart", config={"displayModeBar": False}),
            ]),
        ]),
    ])
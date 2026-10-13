from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dash import Dash, Input, Output, State, dcc, html
from dash.exceptions import PreventUpdate

BASE = Path(__file__).resolve().parent      
P = BASE / "data" / "processed"
drivers = pd.read_csv(P / "drivers.csv")
teams = pd.read_csv(P / "teams.csv")
d_cum = pd.read_csv(P / "driver_cumulative_points.csv", index_col=0)
t_cum = pd.read_csv(P / "team_cumulative_points.csv", index_col=0)
events = pd.read_csv(P / "events.csv")
stats = pd.read_csv(P / "verstappen_stats.csv", index_col=0)["value"]

round_names = events.set_index("RoundNumber")["EventName"].to_dict()

results = pd.read_csv(
    BASE / "data" / "Results.csv",
    usecols=["Abbreviation", "FullName", "TeamName", "TeamColor",
             "Position", "GridPosition", "Points", "RoundNumber"],
)

RED = "#E10600"
BG = "#15151E"
PANEL = "#1F1F2B"
TEXT = "#F2F2F2"
MUTED = "#9A9AAA"
FONT = "'Titillium Web', 'Segoe UI', Arial, sans-serif"

def pick_color(abbr, team_color):
    return "#" + str(team_color)

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
    seen_colors = set()
    for _, row in table.iterrows():
        series = cut(cum[row[key]])
        x = [0] + [int(r) for r in series.index]
        y = [0] + series.tolist()
        hover = ["Szezonrajt"] + [round_names.get(int(r), "") for r in series.index]
        color = "#" + row["TeamColor"]
        is_ver = mode == "drivers" and row["Abbreviation"] == "VER"
        dash = "dot" if color in seen_colors and mode == "drivers" else "solid"
        seen_colors.add(color)
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

    max_points = max(cut(cum[row[key]]).max() for _, row in table.iterrows())
    n_rounds = int(cut(cum).index.max())

    fig.update_layout(
        paper_bgcolor=PANEL, plot_bgcolor=PANEL, font=dict(color=TEXT, family=FONT),
        margin=dict(l=50, r=20, t=20, b=50), height=560, hovermode="closest",
        xaxis=dict(title="Futam sorszáma", gridcolor="#2E2E3E", dtick=2, range=[0, n_rounds]),
        yaxis=dict(title="Összpontszám", gridcolor="#2E2E3E", range=[0, max_points]),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
    )
    return fig

# ------------------------------------------------------------------- Dobogó
def podium_block(place: int, name: str, subtitle: str, points: float, color: str, height: int):
    return html.Div(style={"flex": "1", "textAlign": "center", "alignSelf": "flex-end"}, children=[
        html.Div(name, style={"fontWeight": "700", "fontSize": "18px"}),
        html.Div(subtitle, style={"color": MUTED, "fontSize": "13px", "marginBottom": "6px"}),
        html.Div(f"{points:.0f} pont", style={"color": color, "fontWeight": "700", "marginBottom": "8px"}),
        html.Div(str(place), style={
            "height": f"{height}px", "background": f"linear-gradient(180deg, {color}, #00000055)",
            "borderRadius": "6px 6px 0 0", "fontSize": "52px", "fontWeight": "900",
            "fontStyle": "italic", "paddingTop": "10px",
        }),
    ])

def podium(mode: str = "drivers", round_no=None):
    top = standings(mode, round_no).head(3).reset_index(drop=True)
    if mode == "drivers":
        items = [
            (r["FullName"], r["TeamName"], r["TotalPoints"], "#" + r["TeamColor"])
            for _, r in top.iterrows()
        ]
    else:
        items = [
            (r["TeamName"], "Konstruktőr", r["TotalPoints"], "#" + r["TeamColor"])
            for _, r in top.iterrows()
        ]

    order = [(2, 1, 110), (1, 0, 160), (3, 2, 80)]
    return html.Div(
        style={"display": "flex", "gap": "12px", "alignItems": "flex-end"},
        children=[podium_block(place, *items[idx], height) for place, idx, height in order],
    )


# ---------------------------------------------------------- Oldalsó adatpanel
def stat_row(label, value, size=30):
    return html.Div(style={"borderBottom": "1px solid #2E2E3E", "padding": "10px 0"}, children=[
        html.Div(label, style={"color": MUTED, "fontSize": "12px", "textTransform": "uppercase", "letterSpacing": "1px"}),
        html.Div(str(value), style={"fontSize": f"{size}px", "fontWeight": "900", "fontStyle": "italic"}),
    ])

def season_stats_children():
    wins, races = int(stats["wins"]), int(stats["races"])
    return [
        html.H3("Szezon adatai", style={"margin": "0 0 8px", "textTransform": "uppercase"}),
        stat_row("Futamok", races),
        stat_row("Győzelmek", f"{wins}  ({wins / races:.0%})"),
        stat_row("Dobogók", int(stats["podiums"])),
        stat_row("Pole pozíciók", int(stats["poles"])),
        stat_row("Leggyorsabb körök", int(stats["fastest_laps"])),
        stat_row("Megtett körök", f"{int(stats['laps_completed']):,}".replace(",", " ")),
    ]
 
def side_panel():
    return html.Div(id="side-panel", style={"background": PANEL, "padding": "20px", "borderRadius": "8px",
                                            "borderTop": f"4px solid {RED}"},
                    children=season_stats_children())

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
        projection_rotation=dict(lon=20, lat=25, roll=0),
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
        uirevision="globe",
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
 
 
def lap_section(rn):
    fastest_driver = _get(rn, "fastest_driver")
    tiles = [tile("Verstappen leggyorsabb köre", _get(rn, "ver_best"),
                  _get(rn, "ver_best_lap_no", "{:.0f}. kör"), RED)]
    if fastest_driver == "VER":
        tiles.append(tile("Futam leggyorsabb köre", _get(rn, "fastest_time"), "Verstappen futotta"))
    else:
        tiles.append(tile("Futam leggyorsabb köre", _get(rn, "fastest_time"),
                          f"{fastest_driver} · {_get(rn, 'fastest_lap_no', '{:.0f}. kör')}"))
    tiles += [tile("Mezőny átlagos köre", _get(rn, "avg_all"), "107%-on belüli körök"),
              tile("Verstappen átlagos köre", _get(rn, "ver_avg"), "107%-on belüli körök")]
    return [section_title("Köridők"), tile_grid(tiles)]
 
 
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
 
 
def telemetry_figure(rn):
    f = P / "telemetry" / f"round_{rn:02d}.csv"
    if not f.exists():
        return None
    t = pd.read_csv(f)
    fig = make_subplots(rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.04,
                        row_heights=[0.4, 0.2, 0.2, 0.2],
                        subplot_titles=("Sebesség (km/h)", "Gáz (%)", "Fék", "Sebességfokozat"))
    x = t["Distance"]
    fig.add_trace(go.Scatter(x=x, y=t["Speed"], line=dict(color=RED, width=2), name="Sebesség"), 1, 1)
    fig.add_trace(go.Scatter(x=x, y=t["Throttle"], line=dict(color="#2ECC71", width=2), name="Gáz"), 2, 1)
    fig.add_trace(go.Scatter(x=x, y=t["Brake"].astype(int) * 100, line=dict(color="#F1C40F", width=2),
                             fill="tozeroy", name="Fék"), 3, 1)
    fig.add_trace(go.Scatter(x=x, y=t["nGear"], line=dict(color="#3498DB", width=2, shape="hv"),
                             name="Fokozat"), 4, 1)
    fig.update_xaxes(title_text="Megtett táv a körben (m)", row=4, col=1)
    fig.update_yaxes(gridcolor="#2E2E3E")
    fig.update_xaxes(gridcolor="#2E2E3E")
    fig.update_layout(
        paper_bgcolor=PANEL, plot_bgcolor=PANEL, font=dict(color=TEXT, family=FONT),
        height=620, showlegend=False, hovermode="x unified", margin=dict(l=50, r=20, t=30, b=40))
    fig.update_annotations(font=dict(size=12, color=MUTED))
    return fig
 
 
def build_extra(rn: int):
    """A földgömb alatti kártya tartalma egy adott futamhoz."""
    fig = telemetry_figure(rn)
    if summary.empty:
        body = [html.Div("Futtasd előbb a dataset.py-t, hogy elkészüljön a race_summary.csv.",
                         style={"color": MUTED})]
    else:
        body = lap_section(rn) + weather_section(rn) + [section_title("Verstappen telemetriája – leggyorsabb kör")]
        body.append(dcc.Graph(figure=fig, config={"displayModeBar": False}) if fig is not None
                    else html.Div("Nincs telemetria ehhez a futamhoz (pl. kiesés).", style={"color": MUTED}))
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
 
 
def home_layout():
    return html.Div(children=[
        html.Div(style={"borderLeft": f"8px solid {RED}", "paddingLeft": "16px", "marginBottom": "24px"}, children=[
            html.H1("Max Verstappen 2023-as Forma 1-es dominanciája",
                    style={"margin": 0, "fontStyle": "italic", "textTransform": "uppercase"}),
            html.Div("avagy egy rekorddöntő szezon statisztikája", style={"color": MUTED}),
        ]),
        html.Div(style={"display": "flex", "gap": "24px", "alignItems": "flex-start"}, children=[
            html.Div(style={"flex": "3", "display": "flex", "flexDirection": "column", "gap": "24px"}, children=[
                #Földgömb
                html.Div(style=card, children=[
                    html.H3("A 2023-as naptár", style={"marginTop": 0, "textTransform": "uppercase"}),
                    html.Div("Vidd az egeret egy futam fölé az oldalsó panelhez, kattints a részletes oldalért.",
                             style={"color": MUTED, "fontSize": "13px", "marginBottom": "8px"}),
                    dcc.Graph(id="globe", figure=build_globe(), config={"displayModeBar": False}),
                ]),
                #Dobogó
                html.Div(style=card, children=[
                    html.Div(style=header_row, children=[
                        html.H3("Végeredmény", style={"margin": 0, "textTransform": "uppercase"}),
                        mode_radio("podium-mode"),
                    ]),
                    html.Div(id="podium-container", style={"marginTop": "20px"}, children=podium("drivers")),
                ]),
                #Vonaldiagram
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
 
 
#----------------------------------------------Futam
def race_page(rn: int):
    ev = events[events["RoundNumber"] == rn].iloc[0]
    return html.Div(children=[
        dcc.Link("← Vissza a naptárhoz", href="/",
                 style={"color": RED, "fontWeight": "700", "textDecoration": "none",
                        "textTransform": "uppercase", "fontSize": "13px"}),
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
    

@app.callback(Output("page", "children"), Input("url", "pathname"))
def route(path):
    if path and path.startswith("/race/"):
        rn = round_from_path(path)
        if rn is not None:
            return race_page(rn)
    return home_layout()
 
 
# földgömb click
@app.callback(Output("url", "pathname"), Input("globe", "clickData"), prevent_initial_call=True)
def go_to_race(click):
    if not click:
        raise PreventUpdate
    return f"/race/{int(click['points'][0]['customdata'][0])}"
 
 
# Földgöm hover
@app.callback(Output("side-panel", "children"), Input("globe", "hoverData"))
def hover_side(hover):
    if not hover:
        return season_stats_children()
    return hover_panel_children(int(hover["points"][0]["customdata"][0]))
 
 
# futam-oldal
@app.callback(Output("r-podium-container", "children"),
              Input("r-podium-mode", "value"), State("url", "pathname"))
def update_race_podium(mode, path):
    rn = round_from_path(path)
    if rn is None:
        raise PreventUpdate
    return podium(mode, rn)
 
 
@app.callback(Output("r-line-chart", "figure"),
              Input("r-line-mode", "value"), State("url", "pathname"))
def update_race_chart(mode, path):
    rn = round_from_path(path)
    if rn is None:
        raise PreventUpdate
    return build_line_chart(mode, rn) 
 
# főoldal
@app.callback(Output("line-chart", "figure"), Input("mode", "value"))
def update_chart(mode):
    return build_line_chart(mode)
 
@app.callback(Output("podium-container", "children"), Input("podium-mode", "value"))
def update_podium(mode):
    return podium(mode)

if __name__ == "__main__":
    app.run(debug=True)
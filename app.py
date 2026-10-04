from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, dcc, html

P = Path("data/processed")
drivers = pd.read_csv(P / "drivers.csv")
teams = pd.read_csv(P / "teams.csv")
d_cum = pd.read_csv(P / "driver_cumulative_points.csv", index_col=0)
t_cum = pd.read_csv(P / "team_cumulative_points.csv", index_col=0)
events = pd.read_csv(P / "events.csv")
stats = pd.read_csv(P / "verstappen_stats.csv", index_col=0)["value"]

round_names = events.set_index("RoundNumber")["EventName"].to_dict()

results = pd.read_csv(
    "data/Results.csv",
    usecols=["Abbreviation", "FullName", "TeamName", "TeamColor",
             "Position", "GridPosition", "Points", "RoundNumber"],
)

RED = "#E10600"
BG = "#15151E"
PANEL = "#1F1F2B"
TEXT = "#F2F2F2"
MUTED = "#9A9AAA"
FONT = "'Titillium Web', 'Segoe UI', Arial, sans-serif"


# ---------------------------------------------------------------- Vonaldiagram
def build_line_chart(mode: str) -> go.Figure:
    if mode == "drivers":
        table, cum, key, name_col = drivers, d_cum, "Abbreviation", "Abbreviation"
    else:
        table, cum, key, name_col = teams, t_cum, "TeamName", "TeamName"

    fig = go.Figure()
    seen_colors = set()
    for _, row in table.iterrows():
        series = cum[row[key]]
        x = [0] + [int(r) for r in series.index]
        y = [0] + series.tolist()
        hover = ["Szezonrajt"] + [round_names.get(int(r), "") for r in series.index]
        color = color = "#" + row["TeamColor"]
        is_ver = mode == "drivers" and row["Abbreviation"] == "VER"
        # azonos színű csapattárs szaggatott vonalat kap
        dash = "dot" if color in seen_colors and mode == "drivers" else "solid"
        seen_colors.add(color)
        fig.add_trace(go.Scatter(
            x=x, y=y, mode="lines+markers", name=row[name_col],
            line=dict(color=color, width=3 if is_ver else 2.5, dash=dash),
            marker=dict(
                size=[0] + [12 if is_ver else 8] * len(series),  # az első (0. pont) rejtve marad
                color=color,
                line=dict(color=PANEL, width=1),                # vékony körvonal a jobb olvashatóságért
            ),
            customdata=hover,
            hovertemplate=("<b>%{fullData.name}</b><br>"
                "%{customdata}<br>"
                "<b>%{y:.0f} pont</b><extra></extra>"),
            cliponaxis=False,
        ))

#Diagram stílusa, axis labels
    max_points = max(cum[row[key]].max() for _, row in table.iterrows())
    n_rounds = int(cum.index.max())

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

def podium(mode: str = "drivers"):
    if mode == "drivers":
        top = drivers.head(3).reset_index(drop=True)
        items = [
            (r["FullName"], r["TeamName"], r["TotalPoints"],
             "#" + r["TeamColor"])
            for _, r in top.iterrows()
        ]
    else:
        top = teams.head(3).reset_index(drop=True)
        items = [
            (r["TeamName"], "Konstruktőr", r["TotalPoints"],
            "#" + r["TeamColor"])
            for _, r in top.iterrows()
        ]

    # megjelenítési sorrend: 2. – 1. – 3.
    order = [(2, 1, 110), (1, 0, 160), (3, 2, 80)]
    return html.Div(
        style={"display": "flex", "gap": "12px", "alignItems": "flex-end"},
        children=[podium_block(place, *items[idx], height) for place, idx, height in order],
    )


# ---------------------------------------------------------- Oldalsó adatpanel
def stat_row(label, value):
    return html.Div(style={"borderBottom": "1px solid #2E2E3E", "padding": "10px 0"}, children=[
        html.Div(label, style={"color": MUTED, "fontSize": "12px", "textTransform": "uppercase", "letterSpacing": "1px"}),
        html.Div(str(value), style={"fontSize": "30px", "fontWeight": "900", "fontStyle": "italic"}),
    ])


def side_panel():
    wins, races = int(stats["wins"]), int(stats["races"])
    return html.Div(style={"background": PANEL, "padding": "20px", "borderRadius": "8px",
                           "borderTop": f"4px solid {RED}"}, children=[
        html.H3("Szezon adatai", style={"margin": "0 0 8px", "textTransform": "uppercase"}),
        stat_row("Futamok", races),
        stat_row("Győzelmek", f"{wins}  ({wins / races:.0%})"),
        stat_row("Dobogók", int(stats["podiums"])),
        stat_row("Pole pozíciók", int(stats["poles"])),
        stat_row("Leggyorsabb körök", int(stats["fastest_laps"])),
        stat_row("Megtett körök", f"{int(stats['laps_completed']):,}".replace(",", " ")),
    ])

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


def fmt_pos(value):
    return f"P{int(value)}" if pd.notna(value) and value > 0 else "–"


def race_detail(round_no: int):
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

    return html.Div(children=[
        html.Div(f"{int(ev['RoundNumber'])}. forduló", style={"color": RED, "fontWeight": "700",
                                                              "textTransform": "uppercase", "fontSize": "12px"}),
        html.H3(ev["EventName"], style={"margin": "2px 0"}),
        html.Div(f"{ev['Location']}, {ev['Country']} · {str(ev['EventDate'])[:10]}",
                 style={"color": MUTED, "fontSize": "13px", "marginBottom": "12px"}),
        *rows,
        html.Div(ver_line, style={"marginTop": "14px", "fontWeight": "700", "color": RED}),
    ])


# --------------------------------------------------------------------- APP LAYOUT
app = Dash(__name__)
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

PLACEHOLDER = html.Div("Egyes futamok részletes adatai a földgömbre kattintás után jelennek meg.",
                       style={"color": MUTED, "paddingTop": "40px", "textAlign": "center"})

app.layout = html.Div(style={"background": BG, "color": TEXT, "fontFamily": FONT,
                             "minHeight": "100vh", "padding": "24px 40px"}, children=[
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
                html.Div(style={"display": "flex", "gap": "20px", "alignItems": "stretch"}, children=[
                    html.Div(style={"flex": "2", "minWidth": 0}, children=[
                        dcc.Graph(id="globe", figure=build_globe(), config={"displayModeBar": False}),
                    ]),
                    html.Div(id="race-detail", style={"flex": "1", "minWidth": "240px"}, children=PLACEHOLDER),
                ]),
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

@app.callback(Output("line-chart", "figure"), Input("mode", "value"))
def update_chart(mode):
    return build_line_chart(mode)

@app.callback(Output("podium-container", "children"), Input("podium-mode", "value"))
def update_podium(mode):
    return podium(mode)

@app.callback(Output("race-detail", "children"), Input("globe", "clickData"))
def show_race(click):
    if not click:
        return PLACEHOLDER
    round_no = int(click["points"][0]["customdata"][0])
    return race_detail(round_no)

if __name__ == "__main__":
    app.run(debug=True)
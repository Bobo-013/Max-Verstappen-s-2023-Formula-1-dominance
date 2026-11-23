import json
import time
from urllib.parse import quote, unquote

from dash import ALL, Dash, Input, Output, State, ctx, dcc, html
from dash.exceptions import PreventUpdate

from compare_page import group_page, similar_page
from components import build_line_chart, session_podium
from config import (ANTHEM_S, ANTHEM_VOL, BG, FONT, INTERVAL_MS, LAP_DELAY, MUTED, PAGE_IN_S,
                    PAGE_OUT_S, PANEL, RED, START_LON, STEP_DEG, TEXT, THEME_FILE, THEME_VOL)
from data import BASE, SESS, TYRE_IMGS, round_names, session_from_path
from home_page import home_layout, hover_panel_children, season_stats_children
from race_page import race_page
from race_telemetry import telemetry_figure
from race_weather import CRITERIA, similar_races, wx_card
from summary_page import summary_page
from template import INDEX_TEMPLATE, _delta_css, _lap_css


app = Dash(__name__, suppress_callback_exceptions=True, assets_folder=str(BASE / "assets"))
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
    html.Div(id="page")
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
    if path == "/summary":
        return summary_page()
    if path and path.startswith("/group/"):
        parts = path.strip("/").split("/")
        if len(parts) >= 3:
            return group_page(parts[1], unquote(parts[2]))

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
    cards = [wx_card(k, rn, active, s) for k in CRITERIA]
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

# ---------------------------------------------------------- Összegző oldal callbackek
# Kategória oszlopára kattintás -> a kategória oldala
@app.callback(Output("url", "pathname", allow_duplicate=True),
              Input({"type": "cat-graph", "kind": ALL}, "clickData"),
              prevent_initial_call=True)
def go_group(_):
    trig = ctx.triggered_id
    data = ctx.triggered[0]["value"] if ctx.triggered else None
    if not trig or not data:
        raise PreventUpdate
    label = data["points"][0]["x"]
    return f"/group/{trig['kind']}/{quote(str(label), safe='')}"
 
if __name__ == "__main__":
    app.run(debug=True)
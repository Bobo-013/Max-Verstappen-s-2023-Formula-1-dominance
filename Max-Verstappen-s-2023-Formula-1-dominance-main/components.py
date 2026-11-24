import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html

from config import BG, FONT, MUTED, PANEL, PODIUM_DELAY, RED, TEAM_ANTHEM, TEXT, WINNER_ANTHEM
from data import BASE, SESS, drivers, d_cum, events, round_names, sess_url, t_cum, teams
from helpers import (_anthem_marker, _hex, _team_rank, fmt_pos, pick_color, standings)


# 4. Közös diagramok és kártyák (főoldal és futamoldal is használja)
 
# A pontok alakulása vonaldiagramon. mode: "drivers" / "teams".
# Ha upto meg van adva, csak az adott futamig rajzol.
def build_line_chart(mode: str, upto=None) -> go.Figure:
    if mode == "drivers":
        table, cum, key, name_col = drivers, d_cum, "Abbreviation", "FullName"
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
        margin=dict(l=0, r=0, t=50, b=0), height=520,
        hoverlabel=dict(font_size=15, font_family=FONT),
        legend=dict(orientation="v", x=1, xanchor="left", y=1, yanchor="top",
                    bgcolor="rgba(0,0,0,0)", font=dict(size=12),
                    itemsizing="constant", tracegroupgap=0,),
    )
    fig.update_xaxes(gridcolor="#2E2E3E")
    fig.update_yaxes(gridcolor="#2E2E3E")
    return fig
 
 
# ---------------------------------------------------------- Eredmény kártya.
# A header=True a futam címét is kiírja (oldalsáv).
def _best_txt(r):
    b = r.get("Best")
    return b if isinstance(b, str) and b else "–"

def race_detail(round_no: int, header: bool = True, s: str = "R"):
    ev = events[events["RoundNumber"] == round_no].iloc[0]
    res = SESS[s]["results"]
    res = res[res["RoundNumber"] == round_no].sort_values("Position")
    top3 = res.head(3).reset_index(drop=True)

    rows = []
    for i, r in top3.iterrows():
        color = pick_color(r["Abbreviation"], r["TeamColor"])
        right = _best_txt(r) if s == "Q" else f"{r['Points']:.0f} p"
        rows.append(html.Div(style={"display": "flex", "alignItems": "center", "gap": "10px",
                                    "padding": "8px 0", "borderBottom": "1px solid #2E2E3E"}, children=[
            html.Div(str(i + 1), style={"fontSize": "26px", "fontWeight": "900", "fontStyle": "italic",
                                        "color": color, "width": "28px"}),
            html.Div(children=[
                html.Div(r["FullName"], style={"fontWeight": "700"}),
                html.Div(r["TeamName"], style={"color": MUTED, "fontSize": "12px"}),
            ]),
            html.Div(right, style={"marginLeft": "auto", "fontWeight": "700"}),
        ]))

    ver = res[res["Abbreviation"] == "VER"]
    ver_line = ""
    if not ver.empty:
        v = ver.iloc[0]
        if s == "Q":
            ver_line = f"Verstappen: {fmt_pos(v['Position'])} · {_best_txt(v)}"
        else:
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

# Időmérő · Sprint · Futam váltó (csak akkor jelenik meg, ha az adott fordulóban több session van)
def session_tabs(rn, s):
    tabs = []
    for k in ("Q", "S", "R"):
        if k not in SESS or rn not in SESS[k]["rounds"]:
            continue
        on = k == s
        tabs.append(dcc.Link(SESS[k]["label"], href=sess_url(rn, k), style={
            "padding": "5px 14px", "borderRadius": "999px", "fontSize": "12px", "fontWeight": "700",
            "textTransform": "uppercase", "textDecoration": "none",
            "background": RED if on else BG, "color": TEXT if on else MUTED,
            "border": f"1px solid {RED if on else '#2E2E3E'}"}))
    if len(tabs) < 2:
        return html.Div()
    return html.Div(tabs, style={"display": "flex", "gap": "8px", "marginBottom": "14px"})
 
 
# ---------------------------------------------------------- Dobogó
# (helyezés, hányadik elem a listában, oszlopmagasság)
PODIUM_ORDER = [(2, 1, 110), (1, 0, 160), (3, 2, 80)]


# A dobogó három oszlopa egy sorban. Elemek: (név, alcím, érték szöveg, szín)
def _podium_row(items, extra=()):
    return html.Div(
        style={"display": "flex", "gap": "12px", "alignItems": "flex-end", "minHeight": "270px"},
        children=[*extra,
                  *[podium_block(place, *items[idx], height)
                    for place, idx, height in PODIUM_ORDER if idx < len(items)]],
    )


# Bajnoki dobogó (főoldal). mode: "drivers" / "teams".
# Ha round_no meg van adva, az akkori állást mutatja.
def podium(mode: str = "drivers", round_no=None, anthem=False):
    top = standings(mode, round_no).head(3).reset_index(drop=True)
    if mode == "drivers":
        items = [
            (r["FullName"], r["TeamName"], f"{r['TotalPoints']:.0f} pont",
             pick_color(r["Abbreviation"], r["TeamColor"]))
            for _, r in top.iterrows()
        ]
    else:
        items = [
            (r["TeamName"], "Konstruktőr", f"{r['TotalPoints']:.0f} pont", "#" + r["TeamColor"])
            for _, r in top.iterrows()
        ]
    extra = []
    if anthem and not top.empty:
        first = top.iloc[0]
        src = (anthem_for(first["Abbreviation"]) if mode == "drivers"
               else team_anthem_for(first["TeamName"]))
        extra = [_anthem_marker(src)]
    return _podium_row(items, extra=extra)


# A dobogó egy oszlopa a felirattal
def podium_block(place: int, name: str, subtitle: str, value: str, color: str, height: int):
    d = PODIUM_DELAY[place]
    return html.Div(style={"flex": "1", "textAlign": "center", "alignSelf": "flex-end"}, children=[
        html.Div(className="podium-text", style={"animationDelay": f"{d + 0.3}s"}, children=[
            html.Div(name, style={"fontWeight": "700", "fontSize": "18px"}),
            html.Div(subtitle, style={"color": MUTED, "fontSize": "13px", "marginBottom": "6px"}),
            html.Div(value, style={"color": color, "fontWeight": "700", "marginBottom": "8px"}),
        ]),
        # az oszlop nulláról nő a célmagasságig
        html.Div(str(place), className="podium-bar", style={
            "height": f"{height}px", "animationDelay": f"{d}s",
            "background": f"linear-gradient(180deg, {color}, #00000055)",
            "borderRadius": "6px 6px 0 0", "fontSize": "52px", "fontWeight": "900",
            "fontStyle": "italic", "paddingTop": "10px", "overflow": "hidden",
        }),
    ])


# A himnusz fájl elérési útja
def _anthem_path(code) -> str:
    if code and (BASE / "assets" / "anthems" / f"{code}.mp3").exists():
        return f"/assets/anthems/{code}.mp3"
    return ""


# A himnusz egy pilótához
def anthem_for(abbr) -> str:
    return _anthem_path(WINNER_ANTHEM.get(abbr))


# A himnusz egy csapathoz
def team_anthem_for(team) -> str:
    return _anthem_path(TEAM_ANTHEM.get(team))


# Egy session (futam / sprint / időmérő) első 3 helyezettje.
# Elemek: (név, alcím, érték szöveg, szín, pilóta rövidítése)
def session_standings(rn: int, s: str = "R", mode: str = "drivers"):
    res = SESS[s]["results"]
    res = res[res["RoundNumber"] == rn].copy()
    res["Position"] = pd.to_numeric(res["Position"], errors="coerce")
    res = res[res["Position"] > 0].sort_values("Position")

    if mode == "drivers":
        return [(r["FullName"], r["TeamName"],
                 _best_txt(r) if s == "Q" else f"{r['Points']:.0f} pont",
                 pick_color(r["Abbreviation"], r["TeamColor"]), r["Abbreviation"])
                for _, r in res.head(3).iterrows()]

    # Konstruktőrök: a győztes pilóta csapata az első, utána a session pontjai szerint
    rows = []
    for team, grp in res.groupby("TeamName", sort=False):
        best = grp.iloc[0]                      # a csapat legjobb helyezettje
        pts = grp["Points"].sum() if "Points" in grp.columns else 0
        rows.append((team, pts, best))

    win_team = res.iloc[0]["TeamName"] if not res.empty else None
    if s == "Q":
        rows.sort(key=lambda x: x[2]["Position"])
    else:
        rows.sort(key=lambda x: (x[0] != win_team, -x[1], x[2]["Position"]))

    return [(team, "Konstruktőr",
             _best_txt(best) if s == "Q" else f"{pts:.0f} pont",
             _hex(best["TeamColor"]), best["Abbreviation"])
            for team, pts, best in rows[:3]]

# A futamoldal dobogója: az adott session eredménye + a himnusz jelölő eleme.
# Himnusz: pilótáknál a győztesé, konstruktőrnél a győztes csapat legjobb pilótájáé.
def session_podium(mode: str, rn: int, s: str = "R"):
    items = session_standings(rn, s, mode)
    if not items:
        src = ""
    elif mode == "teams":
        src = team_anthem_for(items[0][0])
    else:
        src = anthem_for(items[0][4])
    return _podium_row([it[:4] for it in items], extra=[_anthem_marker(src)])
from dash import dcc, html

from charts import bar_chart, bar_fig
from config import MUTED, RED, card
from data import SESS, round_names, wx_icon
from helpers import lap_sec, num_facts, section_title
from race_laps import lap_rows_data
from race_weather import CRITERIA, similar_races
from data import sess_url


# A hasonló időjárási adatokkal rendelkező futamok új oldlaon való megjelenítése

def rel_laps(rounds, s="R"):
    """Eltérés Verstappen legjobb körétől másodpercben (negatív = gyorsabb)."""
    ver_avg, field, rival = [], [], []
    for r in rounds:
        vb = lap_sec(r, "ver_best", s)

        def diff(v):
            return None if (v is None or vb is None) else v - vb

        others = [row[3] for row in (lap_rows_data(r, s) or [])
          if row[0] not in ("Max Verstappen", "Mezőny")]
        ver_avg.append(diff(lap_sec(r, "ver_avg",s)))
        field.append(diff(lap_sec(r, "avg_all", s)))
        rival.append(diff(min(others)) if others else None)
    return {"VER átlag": ver_avg, "Mezőny átlag": field, "Legjobb köridő": rival}


def _fmt_delta(v):
    return f"{v:+.3f} s" if v is not None else "–"


def lap_delta_fig(rounds, rn, s="R"):
    real = rel_laps(rounds, s)
    vals = [v for vs in real.values() for v in vs if v is not None] or [0]
    lo, hi = min(0, min(vals)), max(0, max(vals))
    pad = max((hi - lo) * 0.1, 0.2)
    return bar_fig("Eltérés Verstappen legjobb körétől (s)", rounds, rn, real,
                   unit=" s", fmt=_fmt_delta, yrange=(lo - pad, hi + pad))

def similar_laps(rounds, rn, s="R"):
    return [
        section_title("Köridők"),
        html.Div("Az értékek Verstappen futamonkénti legjobb köréhez viszonyított eltérést mutatják",
                 style={"color": MUTED, "fontSize": "12px", "marginBottom": "10px"}),
        html.Div(style=card, children=[
            dcc.Graph(id="lap-delta-graph", className="bar-anim nav-chart",
                figure=lap_delta_fig(rounds, rn, s),
                config={"displayModeBar": False}, style={"height": "440px"}),]
        )]

BAND_RANGES = {"< 30 °C": (-99, 30), "30–40 °C": (30, 40), "> 40 °C": (40, 99)}

# Az összehasonlító diagramok egy futamlistához
def compare_blocks(rounds, rn, s="R"):
    nums = {r: num_facts(r, s) for r in rounds}

    def col(k):
        return [nums[r][k] for r in rounds]

    charts = []
    if "air" in CRITERIA or "track" in CRITERIA:
        charts.append(bar_chart("Hőmérséklet", rounds, rn,
                                {"Levegő": col("air"), "Aszfalt": col("track")}, unit=" °C"))
    if "humidity" in CRITERIA:
        charts.append(bar_chart("Páratartalom", rounds, rn,
                                {"Páratartalom": col("humidity")}, unit=" %"))
    if "wind" in CRITERIA:
        charts.append(bar_chart("Szél", rounds, rn, {"Szél": col("wind")}, unit=" m/s"))
    charts.append(bar_chart("Verstappen: rajt → cél", rounds, rn,
                            {"Rajtpozíció": col("grid"), "Célpozíció": col("finish")},
                            reverse=True))
    return [*similar_laps(rounds, rn, s),
            html.Div(charts, style={"display": "grid", "gap": "20px", "marginTop": "20px",
                                    "gridTemplateColumns": "repeat(auto-fit, minmax(480px, 1fr))"})]


# Egy kategória (időjárás / aszfalthőmérsékleti sáv) futamai
def group_rounds(kind, label):
    sm = SESS["R"]["summary"]
    if kind == "condition" and "condition" in sm.columns:
        mask = sm["condition"] == label
    elif kind == "track" and "track_temp" in sm.columns and label in BAND_RANGES:
        lo, hi = BAND_RANGES[label]
        mask = (sm["track_temp"] > lo) & (sm["track_temp"] <= hi)
    else:
        return []
    return sorted(int(r) for r in sm.index[mask] if int(r) in SESS["R"]["rounds"])


def group_page(kind, label):
    rounds = group_rounds(kind, label)
    title_kids = []
    icon = wx_icon(label) if kind == "condition" else ""
    if icon:
        title_kids.append(html.Img(src=icon, style={"height": "44px", "width": "44px",
                                                    "objectFit": "contain", "marginRight": "12px",
                                                    "verticalAlign": "middle"}))
    title_kids.append(label)
    header = [
        dcc.Link("← Vissza az összegzéshez", href="/summary", style={
            "color": RED, "fontWeight": "700", "textTransform": "uppercase",
            "fontSize": "13px", "textDecoration": "none"}),
        html.H2(title_kids, style={"margin": "30px 0 4px"}),
        html.Div(f"{len(rounds)} futam", style={"color": MUTED, "marginBottom": "20px"}),
    ]
    if not rounds:
        return html.Div(className="page-right", children=header + [
            html.Div("Nincs futam ebben a kategóriában.", style={"color": MUTED})])
    return html.Div(className="page-right", children=header + compare_blocks(rounds, None))

def similar_page(rn, keys, s="R"):
    others = similar_races(rn, keys, s)
    back = dcc.Link("← Vissza a futamhoz", href=sess_url(rn, s),
                    style={"color": RED, "fontWeight": "700", "textTransform": "uppercase",
                           "fontSize": "13px", "textDecoration": "none"})
    crit = ", ".join(CRITERIA[k][1] for k in keys) or "–"
    header = [back,
              html.H2(f"{round_names[rn]} – hasonló időjárású futamok",
                      style={"margin": "30px 0 4px"}),
              html.Div(f"Egyező adatok: {crit} · {len(others)} találat",
                       style={"color": MUTED, "marginBottom": "20px"})]

    if not others:
        return html.Div(className="page-right", children=header + [
            html.Div("Nincs ilyen hasonló futam.", style={"color": MUTED})])

    rounds = sorted([rn] + others)
    return html.Div(className="page-right", children=header + compare_blocks(rounds, rn, s))
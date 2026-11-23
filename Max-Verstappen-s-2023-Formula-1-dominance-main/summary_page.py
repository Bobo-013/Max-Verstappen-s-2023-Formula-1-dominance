import pandas as pd
from dash import dcc, html

from charts import _chart_card, bar_fig, cat_bar
from config import RED
from data import LAPS, SESS, results, round_names, stats
from helpers import tile, tile_grid


# 6. ÖSSZEGZŐ
# Gyors körök
FAST_THR = 1.01   # "nagyon gyors" kör: a futam legjobb körének 101%-án belül

def _n(v):
    return None if v is None or pd.isna(v) else float(v)

def _fmt1(v):
    return f"{v:.1f}" if v is not None else "–"

def _accurate_laps():
    L = LAPS.get("R")
    if L is None:
        return None
    a = L[L["LapSec"].notna()]
    if "IsAccurate" in a.columns:
        a = a[a["IsAccurate"].fillna(False).astype(bool)]
    return a

# Futamonként: Verstappen és a mezőny átlagos körideje (csak pontos körök), és a különbség
def pace_by_round():
    a = _accurate_laps()
    if a is None:
        return pd.DataFrame()
    rows = []
    for rn, g in a.groupby("RoundNumber"):
        v = g.loc[g["Driver"] == "VER", "LapSec"]
        if v.empty:
            continue
        rows.append({"rn": int(rn), "ver": v.mean(), "field": g.loc[g["Driver"] != "VER", "LapSec"].mean()})
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).set_index("rn")
    df["gap"] = df["field"] - df["ver"]          # pozitív = Verstappen gyorsabb
    return df

# A pontos körök hány %-a volt a futam legjobb körének FAST_THR-szorosán belül
def fast_share():
    a = _accurate_laps()
    if a is None:
        return None
    best = a.groupby("RoundNumber")["LapSec"].transform("min")
    a = a.assign(fast=a["LapSec"] <= best * FAST_THR)
    g = a.groupby(["RoundNumber", "Driver"])["fast"]
    out = pd.DataFrame({"share": g.mean() * 100, "n": g.size()})
    return out[out["n"] >= 10]                   # túl kevés kör torzítana


# Összegző oldal
CONS_MAX = 1.07   # a pilóta mediánjának 107%-ánál lassabb köröket (forgalom, hiba) kihagyjuk

# Köridők szórása (s) futamonként és pilótánként, csak pontos körökből
def consistency():
    a = _accurate_laps()
    if a is None:
        return None
    med = a.groupby(["RoundNumber", "Driver"])["LapSec"].transform("median")
    a = a[a["LapSec"] <= med * CONS_MAX]
    g = a.groupby(["RoundNumber", "Driver"])["LapSec"]
    out = pd.DataFrame({"std": g.std(), "n": g.size()})
    return out[out["n"] >= 10]

# Az Összegző oldal layout
def summary_page():
    rounds = SESS["R"]["rounds"]
    res = results
    pace = pace_by_round()
    share = fast_share()
    cards = []

    # ---- Pontszerzés futamonként: VER, PER, mezőny átlaga pilótánként
    piv = res.pivot_table(index="RoundNumber", columns="Abbreviation",
                          values="Points", aggfunc="sum")
    field_avg = res[res["Abbreviation"] != "VER"].groupby("RoundNumber")["Points"].mean()
    def pts(abbr):
        return [_n(piv[abbr].get(r)) if abbr in piv.columns else None for r in rounds]
    pts_series = {"Verstappen": pts("VER"), "Pérez": pts("PER"),
                  "Mezőny átlag": [_n(field_avg.get(r)) for r in rounds]}
    cards.append(_chart_card(
        "Pontszerzés futamonként",
        "Verstappen, Pérez és a mezőny pilótánkénti átlagos pontja. Kattints egy futam nevére a részletekért.",
        bar_fig("Szerzett pont", rounds, None, pts_series, unit=" p", fmt=_fmt1)))

    # ---- Időmérő → rajt → cél (Verstappen)
    ver_r = res[res["Abbreviation"] == "VER"].set_index("RoundNumber")
    quali = SESS.get("Q", {}).get("results")
    q_pos = {}
    if quali is not None:
        q_pos = quali[quali["Abbreviation"] == "VER"].set_index("RoundNumber")["Position"].to_dict()
    def posv(v):
        v = _n(v)
        return v if v and v > 0 else None
    pos_series = {
        "Időmérő": [posv(q_pos.get(r)) for r in rounds],
        "Rajt": [posv(ver_r["GridPosition"].get(r)) for r in rounds],
        "Cél": [posv(ver_r["Position"].get(r)) for r in rounds]}
    cards.append(_chart_card(
        "Időmérő, rajt és cél – Verstappen",
        "Minél magasabb az oszlop, annál jobb a helyezés. Ahol a rajt és az időmérő eltér, ott büntetés vagy kiesés volt.",
        bar_fig("Helyezés", rounds, None, pos_series, reverse=True,
                fmt=lambda v: f"P{v:.0f}" if v is not None else "–")))

    # ---- Gyors körök aránya
    if share is not None and not share.empty:
        sh = share["share"]
        ver_sh, fld_sh = [], []
        for r in rounds:
            try:
                ver_sh.append(float(sh.loc[(r, "VER")]))
            except KeyError:
                ver_sh.append(None)
            try:
                o = sh.loc[r].drop("VER", errors="ignore")
                fld_sh.append(float(o.mean()) if len(o) else None)
            except KeyError:
                fld_sh.append(None)
        cards.append(_chart_card(
            "Gyors körök aránya",
            f"A pontos körök hány %-a volt a futam legjobb körének {int((FAST_THR - 1) * 100)}%-án belül. "
            "A mezőny átlaga a többi pilóta átlaga (legalább 10 pontos körrel).",
            bar_fig("Gyors körök (%)", rounds, None,
                    {"Verstappen": ver_sh, "Mezőny átlag": fld_sh}, unit=" %", fmt=_fmt1)))
    
    # ---- Köridők egyenletessége
    cons = consistency()
    if cons is not None and not cons.empty:
        sd = cons["std"]
        ver_sd, fld_sd = [], []
        for r in rounds:
            try:
                ver_sd.append(float(sd.loc[(r, "VER")]))
            except KeyError:
                ver_sd.append(None)
            try:
                o = sd.loc[r].drop("VER", errors="ignore")
                fld_sd.append(float(o.mean()) if len(o) else None)
            except KeyError:
                fld_sd.append(None)
        cards.append(_chart_card(
            "Köridők egyenletessége",
            "A pontos körök szórása másodpercben: minél kisebb az oszlop, annál egyenletesebb (gépszerűbb) a tempó. "
            "A mezőny a többi pilóta szórásának átlaga.",
            bar_fig("Köridők szórása (s)", rounds, None,
                    {"Verstappen": ver_sd, "Mezőny átlag": fld_sd},
                    unit=" s", fmt=lambda v: f"{v:.2f} s" if v is not None else "–")))
        
    # ---- Időjárás szerint: mennyivel volt gyorsabb az átlagnál
    if not pace.empty:
        sm = SESS["R"]["summary"]
        pace = pace.copy()
        if "condition" in sm.columns:
            pace["cond"] = [sm["condition"].get(r) for r in pace.index]
            g = pace.dropna(subset=["cond"]).groupby("cond")["gap"].agg(["mean", "count"])
            if not g.empty:
                cards.append(_chart_card(
                    "Verstappen előnye az időjárás szerint",
                    "A mezőny átlagos köridejéből kivonva Verstappenét (pontos körök). "
                    "Vizes futamból kevés volt, ezért az ottani érték csak tájékoztató.",
                    cat_bar("Átlagos előny (s/kör)", g.index.tolist(),
                            g["mean"].tolist(), g["count"].tolist()), nav=False,
                    graph_id={"type": "cat-graph", "kind": "condition"}))
        if "track_temp" in sm.columns:
            pace["tt"] = [_n(sm["track_temp"].get(r)) for r in pace.index]
            p = pace.dropna(subset=["tt"]).copy()
            if not p.empty:
                p["band"] = pd.cut(p["tt"], [-99, 30, 40, 99],
                                   labels=["< 30 °C", "30–40 °C", "> 40 °C"])
                g = p.groupby("band", observed=True)["gap"].agg(["mean", "count"])
                cards.append(_chart_card(
                    "Verstappen előnye az aszfalthőmérséklet szerint",
                    "Ugyanaz a mutató, aszfalthőmérsékleti sávokra bontva.",
                    cat_bar("Átlagos előny (s/kör)", [str(i) for i in g.index],
                            g["mean"].tolist(), g["count"].tolist()), nav=False,
                    graph_id={"type": "cat-graph", "kind": "track"}))
    # ---- Fejléc csempék
    wins, poles = stats.get("wins"), stats.get("poles")
    ver_pts = [v for v in pts_series["Verstappen"] if v is not None]
    tiles = [tile("Győzelem", str(wins) if wins is not None else "–", f"{len(rounds)} futamból", RED),
             tile("Pole pozíció", str(poles) if poles is not None else "–"),
             tile("Átlagos pont / futam", f"{sum(ver_pts) / len(ver_pts):.1f}" if ver_pts else "–", "csak a futamok")]
    if share is not None and not share.empty:
        try:
            v = share["share"].xs("VER", level="Driver").mean()
            tiles.append(tile("Nagyon gyors körök", f"{v:.0f} %", "Verstappen átlaga"))
        except KeyError:
            pass
    if not pace.empty:
        tiles.append(tile("Átlagos előny", f"{pace['gap'].mean():+.2f} s", "a mezőnyhöz képest / kör"))
    # ---- Legnagyobb helyezésnyerés egy futamon
    g = ver_r[(ver_r["GridPosition"] > 0) & (ver_r["Position"] > 0)]
    if not g.empty:
        gain = (g["GridPosition"] - g["Position"])
        best_rn = int(gain.idxmax())
        tiles.append(tile("Legtöbb megelőzés", f"+{int(gain.max())} hely",
                            round_names.get(best_rn, "")))
    if cons is not None and not cons.empty:
        try:
            v = cons["std"].xs("VER", level="Driver").mean()
            tiles.append(tile("Köridő-szórás", f"{v:.2f} s", "Verstappen átlaga"))
        except KeyError:
            pass
        
    return html.Div(className="page-right", children=[
        dcc.Link("← Vissza a naptárhoz", href="/", style={
            "color": RED, "fontWeight": "700", "textTransform": "uppercase",
            "fontSize": "13px", "textDecoration": "none"}),
        html.H2("Szezon összegzése", style={"margin": "30px 0 20px", "textTransform": "uppercase"}),
        tile_grid(tiles),
        html.Div(cards, style={"display": "grid", "gap": "24px", "marginTop": "24px",
                               "gridTemplateColumns": "repeat(auto-fit, minmax(560px, 1fr))"}),
    ])
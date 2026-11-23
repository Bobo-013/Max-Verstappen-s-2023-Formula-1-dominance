import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import dcc, html
from plotly.subplots import make_subplots

from config import (BG, FONT, MUTED, PANEL, PIT_MAX_S, TEXT, TRACK_STATUS,
                    TYRE_COLORS, TYRE_NAMES, card)
from data import LAPS, NAMES, SESS, TYRE_IMGS
from helpers import _rgba, _status_runs, fmt_lap, fmt_pos, section_title


# ---------------------------------------------------------- Stratégia
# Az első 3 és Verstappen stintjei vízszintes sávokon, a pitstopok időivel.
def tyre_figure(rn, s="R"):
    laps = LAPS.get(s)
    if laps is None:
        return None
    L = laps[laps["RoundNumber"] == rn]
    if L.empty:
        return None

    res = SESS[s]["results"]
    res = res[res["RoundNumber"] == rn].sort_values("Position")
    pick = res.head(3)["Abbreviation"].tolist()
    if "VER" not in pick:
        pick.append("VER")
    pos_of = res.set_index("Abbreviation")["Position"].to_dict()

    total_laps = int(L["LapNumber"].max())
    fig = go.Figure()
    seen = set()
    pit_x, pit_y, pit_txt, pit_hover = [], [], [], []
    tick_vals, tick_text = [], []

    for row_i, abbr in enumerate(pick):
        d = L[L["Driver"] == abbr].sort_values("LapNumber")
        if d.empty:
            continue

        stints = []
        for _, g in d.groupby("Stint", sort=True):
            comp = (str(g["Compound"].dropna().iloc[0]).upper()
                    if g["Compound"].notna().any() else "UNKNOWN")
            if comp not in TYRE_COLORS:
                comp = "UNKNOWN"
            stints.append((int(g["LapNumber"].min()), int(g["LapNumber"].max()), comp, g))

        pit_total = 0.0
        for k, (start, end, comp, g) in enumerate(stints):
            n = end - start + 1
            best = g["LapSec"].min()
            best_txt = fmt_lap(best) if pd.notna(best) else "–"
            fig.add_trace(go.Bar(
                x=[n], y=[row_i], base=[start - 1], orientation="h", width=0.55,
                name=TYRE_NAMES[comp], legendgroup=comp, showlegend=comp not in seen,
                text=[str(n)], textposition="inside", insidetextanchor="middle",
                textfont=dict(color="#111", size=12),
                marker=dict(color=TYRE_COLORS[comp], line=dict(color=PANEL, width=2)),
                hovertemplate=(f"<b>{NAMES.get(abbr, abbr)}</b> · {TYRE_NAMES[comp]}<br>"
                               f"{start}–{end}. kör ({n} kör)<br>"
                               f"Legjobb kör ezen a gumin: {best_txt}<extra></extra>"),
            ))
            seen.add(comp)

            # Pitstop a következő stint elején
            if k + 1 < len(stints):
                nxt = stints[k + 1][3]
                t_in = g["PitInTime"].iloc[-1] if "PitInTime" in g else pd.NaT
                t_out = nxt["PitOutTime"].iloc[0] if "PitOutTime" in nxt else pd.NaT
                dur = (t_out - t_in).total_seconds() if pd.notna(t_in) and pd.notna(t_out) else None
                if dur is not None and dur <= 0:
                    dur = None
                if dur is not None:
                    pit_total += dur
                pit_x.append(end)
                pit_y.append(row_i - 0.3)
                pit_txt.append(f"{dur:.1f} s" if dur is not None and dur <= 60 else "")
                pit_hover.append(f"{abbr} · {k + 1}. kiállás ({end}. kör)<br>"
                                 f"Pitben töltött idő: "
                                 f"{f'{dur:.1f} s' if dur is not None else '–'}")

        tick_vals.append(row_i)
        tick_text.append(f"<b>{NAMES.get(abbr, abbr)}</b> ({fmt_pos(pos_of.get(abbr))})<br>"
                         f"{len(stints) - 1} kiállás · {pit_total:.1f} s")

    if not tick_vals:
        return None

    fig.add_trace(go.Scatter(
        x=pit_x, y=pit_y, mode="markers+text", name="Pitstop",
        text=pit_txt, textposition="top center", textfont=dict(size=11, color=TEXT),
        marker=dict(symbol="diamond", size=9, color=TEXT, line=dict(color=BG, width=1)),
        customdata=pit_hover, hovertemplate="%{customdata}<extra></extra>"))

    n_rows = len(tick_vals)
    fig.update_xaxes(range=[0, total_laps + 1], dtick=5, gridcolor="#2E2E3E",
                     title_text="Kör", zeroline=False)
    fig.update_yaxes(tickvals=tick_vals, ticktext=tick_text, range=[n_rows - 0.4, -0.75],
                     showgrid=False, fixedrange=True)
    fig.update_layout(
        barmode="overlay", paper_bgcolor=PANEL, plot_bgcolor=PANEL,
        font=dict(color=TEXT, family=FONT), height=105 * n_rows + 110,
        margin=dict(l=10, r=20, t=40, b=40), hovermode="closest",
        hoverlabel=dict(bgcolor=PANEL, font=dict(family=FONT, color=TEXT)),
        legend=dict(orientation="h", x=1, xanchor="right", y=1.02, yanchor="bottom",
                    bgcolor="rgba(0,0,0,0)"))
    return fig

# Egy pilóta kiállásainak ideje másodpercben (a következő stint PitOutTime-ja mínusz az előző PitInTime-ja).
def _pit_durations(d):
    groups = [g for _, g in d.groupby("Stint", sort=True)]
    out = []
    for a, b in zip(groups, groups[1:]):
        t_in, t_out = a["PitInTime"].iloc[-1], b["PitOutTime"].iloc[0]
        dur = (t_out - t_in).total_seconds() if pd.notna(t_in) and pd.notna(t_out) else None
        out.append(dur if dur is not None and dur > 0 else None)
    return out


# Pilótánként: átlagos pitidő + gumikeverékenként körszám, átlagos és legjobb köridő.
def tyre_stats(rn, s="R"):
    laps = LAPS.get(s)
    if laps is None:
        return []
    L = laps[laps["RoundNumber"] == rn]
    res = SESS[s]["results"]
    res = res[res["RoundNumber"] == rn].sort_values("Position")
    pick = res.head(3)["Abbreviation"].tolist()
    if "VER" not in pick:
        pick.append("VER")
    pos_of = res.set_index("Abbreviation")["Position"].to_dict()

    rows = []
    for abbr in pick:
        d = L[L["Driver"] == abbr].sort_values("LapNumber").copy()
        if d.empty:
            continue
        d["Compound"] = d["Compound"].fillna("UNKNOWN").astype(str).str.upper()
        d.loc[~d["Compound"].isin(TYRE_COLORS), "Compound"] = "UNKNOWN"

        all_pits = _pit_durations(d)
        pits = [p for p in all_pits if p is not None and p <= PIT_MAX_S]

        comps = []
        for comp, g in d.groupby("Compound", sort=False):    
            valid = g[g["LapSec"].notna()]
            if "IsAccurate" in valid.columns:                
                acc = valid[valid["IsAccurate"].fillna(False).astype(bool)]
            else:
                acc = valid
            comps.append(dict(
                comp=comp, laps=len(g), n_acc=len(acc),
                avg=float(acc["LapSec"].mean()) if not acc.empty else None,
                best=float(valid["LapSec"].min()) if not valid.empty else None))

        rows.append(dict(abbr=abbr, name=NAMES.get(abbr, abbr), pos=fmt_pos(pos_of.get(abbr)),
                         pit_avg=sum(pits) / len(pits) if pits else None,
                         n_stops=len(all_pits), comps=comps))
    return rows


# A stratégia adatok megjelenítése
# Köridők eloszlása pilótánként és gumikeverékenként.
def tyre_pace_figure(rn, s="R"):
    laps = LAPS.get(s)
    if laps is None:
        return None
    L = laps[laps["RoundNumber"] == rn]
    stats = tyre_stats(rn, s)
    if L.empty or not stats:
        return None

    titles = []
    for r in stats:
        pit = f"átlagos pitben töltött idő: {r['pit_avg']:.1f} s" if r["pit_avg"] is not None else "nem állt ki"
        titles.append(f"{r['pos']} · {r['n_stops']} kiállás · {pit}")

    n = len(stats)
    fig = make_subplots(rows=n, cols=1, shared_xaxes=True, vertical_spacing=0.10,
                        subplot_titles=titles)
    all_y, seen = [], set()
    pit_marks, status_marks, line_jobs, extras = [], [], [], []
    total_laps = int(L["LapNumber"].max())

    for row, r in enumerate(stats, start=1):
        dfull = L[L["Driver"] == r["abbr"]].sort_values("LapNumber").copy()
        if dfull.empty:
            continue
        dfull["Compound"] = dfull["Compound"].fillna("UNKNOWN").astype(str).str.upper()
        dfull.loc[~dfull["Compound"].isin(TYRE_COLORS), "Compound"] = "UNKNOWN"

        fig.update_yaxes(title_text=f"<b>{r['name']}</b>", title_font=dict(size=13),
                         title_standoff=8, row=row, col=1)

        # Megszakítások
        if "TrackStatus" in dfull.columns:
            for a, b, cls in _status_runs(dfull):
                status_marks.append((row, a, b, cls))

        # Kiállások
        groups = [g for _, g in dfull.groupby("Stint", sort=True)]
        durs = _pit_durations(dfull)
        for k, (g, dur) in enumerate(zip(groups, durs), start=1):
            x = int(g["LapNumber"].max()) + 0.5
            hover = (f"<b>{r['name']}</b> · {k}. kiállás ({int(g['LapNumber'].max())}. kör)<br>"
                     f"Pitben töltött idő: {f'{dur:.1f} s' if dur is not None else '–'}")
            txt = f"{dur:.1f} s" if dur is not None and dur <= PIT_MAX_S else ""
            pit_marks.append((row, x, hover, txt))

        # Minden mért kör
        dall = dfull[dfull["LapSec"].notna()]
        dacc = dall
        if "IsAccurate" in dall.columns:
            dacc = dall[dall["IsAccurate"].fillna(False).astype(bool)]
        if dall.empty or dacc.empty:
            continue
        all_y += dacc["LapSec"].tolist()

        # Stintenként egy vonal; a következő stint az előző utolsó pontjából indul
        prev = None
        for _, g in dall.groupby("Stint", sort=True):
            comp = g["Compound"].iloc[0]
            xs = g["LapNumber"].astype(int).tolist()
            ys = g["LapSec"].astype(float).tolist()
            life = g["TyreLife"].fillna(0).astype(int).tolist()
            if prev is not None:
                xs, ys, life = [prev[0]] + xs, [prev[1]] + ys, [prev[2]] + life
            prev = (xs[-1], ys[-1], life[-1])
            line_jobs.append((row, r, comp, xs, ys, life))

        b = dacc.loc[dacc["LapSec"].idxmin()]
        extras.append((row, float(dacc["LapSec"].mean()), b))

    if not all_y:
        return None

    lo, hi = min(all_y), max(all_y)
    cap = hi + 0.6                        # ennél lassabb köröket a vonal levágja (hoverben a valódi idő)
    y0, y1 = lo - 0.4, hi + 1.6
    y_top = hi + 0.9

    # Megszakítás-sávok
    for row, a, b, cls in status_marks:
        label, color, op = TRACK_STATUS[cls]
        fig.add_trace(go.Scatter(
            x=[a - 0.5, b + 0.5, b + 0.5, a - 0.5, a - 0.5], y=[y0, y0, y1, y1, y0],
            mode="lines", fill="toself", fillcolor=_rgba(color, op + 0.1),
            line=dict(width=0), name=label, legendgroup=f"st-{cls}",
            showlegend=f"st-{cls}" not in seen, hoverinfo="skip",
        ), row=row, col=1)
        seen.add(f"st-{cls}")

    # Köridő-vonalak
    for row, r, comp, xs, ys, life in line_jobs:
        fig.add_trace(go.Scatter(
            x=xs, y=[min(v, cap) for v in ys], mode="lines",
            name=TYRE_NAMES[comp], legendgroup=comp, showlegend=comp not in seen,
            line=dict(color=TYRE_COLORS[comp], width=2.5),
            customdata=np.column_stack([life, [fmt_lap(v) for v in ys]]),
            hovertemplate=(f"<b>{r['name']}</b> · {TYRE_NAMES[comp]}<br>"
                           "%{x}. kör · gumikor: %{customdata[0]}<br>"
                           "Köridő: %{customdata[1]}<extra></extra>"),
        ), row=row, col=1)
        seen.add(comp)

    # Átlag és legjobb kör (a vonalak fölött)
    for row, mean, b in extras:
        fig.add_trace(go.Scatter(
            x=[1, total_laps], y=[mean, mean], mode="lines+text", showlegend="mean" not in seen,
            name="Átlag", legendgroup="mean",
            line=dict(color=MUTED, width=1.5, dash="dash"),
            text=["", f"átlag {fmt_lap(mean)}"], textposition="top left",
            textfont=dict(color=MUTED, size=11),
            hovertemplate=f"Átlag: {fmt_lap(mean)}<extra></extra>",
        ), row=row, col=1)
        seen.add("mean")
        fig.add_trace(go.Scatter(
            x=[int(b["LapNumber"])], y=[float(b["LapSec"])], mode="markers",
            name="Legjobb kör", legendgroup="best", showlegend="best" not in seen,
            marker=dict(symbol="star", size=16, color=TEXT, line=dict(color=BG, width=1)),
            hovertemplate=(f"Legjobb kör: {fmt_lap(float(b['LapSec']))}<br>"
                           f"{int(b['LapNumber'])}. kör · {TYRE_NAMES[b['Compound']]}<extra></extra>"),
        ), row=row, col=1)
        seen.add("best")

    # Kiállás-jelölők
    for row, x, hover, txt in pit_marks:
        fig.add_trace(go.Scatter(
            x=[x, x], y=[y0, y_top], mode="lines+markers+text", cliponaxis=False,
            name="Kiállás", legendgroup="pit", showlegend="pit" not in seen,
            line=dict(color=TEXT, width=1, dash="dot"),
            marker=dict(symbol="diamond", size=[0, 10], color=TEXT, line=dict(color=BG, width=1)),
            text=["", txt], textposition="top center", textfont=dict(size=11, color=TEXT),
            hovertemplate=hover + "<extra></extra>",
        ), row=row, col=1)
        seen.add("pit")

    step = 1 if hi - lo <= 8 else 2 if hi - lo <= 16 else 5
    ticks = list(range(int(lo // step * step), int(hi // step * step + step) + 1, step))
    ticks = [t for t in ticks if y0 <= t <= hi + 0.6]

    fig.update_xaxes(range=[0, total_laps + 1], dtick=5, gridcolor="#2E2E3E", zeroline=False,
                     fixedrange=True)
    fig.update_xaxes(title_text="Kör", row=n, col=1)
    fig.update_yaxes(tickvals=ticks, ticktext=[f"{t // 60}:{t % 60:02d}" for t in ticks],
                     range=[y0, y1], gridcolor="#2E2E3E", zeroline=False, fixedrange=True)
    fig.update_annotations(font=dict(size=12, color=TEXT), xanchor="left", x=0.0)
    fig.update_layout(
        paper_bgcolor=PANEL, plot_bgcolor=PANEL, font=dict(color=TEXT, family=FONT),
        height=250 * n + 90, margin=dict(l=120, r=20, t=90, b=50), hovermode="closest",
        hoverlabel=dict(bgcolor=PANEL, font=dict(family=FONT, color=TEXT)),
        legend=dict(orientation="h", x=0, xanchor="left", y=1.0, yref="container",
                    yanchor="top", bgcolor="rgba(0,0,0,0)", font=dict(size=13)))
    return fig
# Animáció
# Az adott futamon használt gumikeverékek (kép + név), beúszó animációval.
def tyre_legend(rn, s="R"):
    laps = LAPS.get(s)
    if laps is None:
        return html.Div()
    L = laps[laps["RoundNumber"] == rn]
    used = L["Compound"].fillna("UNKNOWN").astype(str).str.upper()
    used = {c if c in TYRE_COLORS else "UNKNOWN" for c in used}
    comps = [c for c in TYRE_NAMES if c in used]
    if not comps:
        return html.Div()

    chips = []
    for i, c in enumerate(comps):
        d = f"{0.3 + i * 0.6}s"
        kids = []
        if c in TYRE_IMGS:
            kids.append(html.Img(src=TYRE_IMGS[c], style={"animationDelay": d}))
        kids.append(html.Div(TYRE_NAMES[c], className="tyre-lbl", style={
            "animationDelay": d,
            "fontWeight": "900", "fontStyle": "italic", "textTransform": "uppercase",
            "color": TYRE_COLORS[c], "fontSize": "15px"}))
        chips.append(html.Div(kids, className="tyre-chip"))

    return html.Div([
        html.Div("A versenyen használt gumikeverékek:", style={"color": MUTED, "fontSize": "12px",
                                                   "letterSpacing": "1px",
                                                   "width": "20%"}),
        *chips], className="tyre-legend")

def tyre_section(rn, s="R"):
    fig = tyre_figure(rn, s)
    if fig is None:
        return None
    box = tyre_pace_figure(rn, s)  
    return html.Div(style=card, children=[
        section_title("Stratégia"),
        html.Div("Az első 3 helyezett és Verstappen stintjei. A sávokon a stint hossza látható, "
                 "a rombuszok a kiállásokat jelölik a pitben töltött idővel.",
                 style={"color": MUTED, "fontSize": "12px", "marginBottom": "8px"}),
        tyre_legend(rn, s),
        html.Div(dcc.Graph(figure=fig, config={"displayModeBar": False}), className="tyre-anim"),
        dcc.Graph(figure=box, config={"displayModeBar": False}) if box else
        html.Div("Nincs elég köridő.", style={"color": MUTED}),
    ])
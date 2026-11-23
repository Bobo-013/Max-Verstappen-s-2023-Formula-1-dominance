import plotly.graph_objects as go
from dash import dcc, html

from config import FONT, MUTED, PANEL, RED, SERIES_COLORS, TEXT, card
from data import round_names, wx_icon
from helpers import fmt_lap


# Kategóriás oszlopdiagram (időjárás / hőmérsékleti sáv)
def cat_bar(title, labels, vals, counts):
    fig = go.Figure(go.Bar(
        x=labels, y=vals, marker={"color": RED},
        text=[f"{v:+.2f} s · {n} futam" for v, n in zip(vals, counts)],
        textposition="outside", cliponaxis=False,
        hovertemplate="%{x}<br>%{text}<extra></extra>"))
    has_icons = False
    for i, lab in enumerate(labels):
        icon = wx_icon(lab)
        if icon:
            has_icons = True
            fig.add_layout_image(dict(
                source=icon, xref="x", yref="paper", x=i, y=-0.1,
                xanchor="center", yanchor="top", sizex=0.7, sizey=0.16))
    fig.update_xaxes(showgrid=False, linecolor="#2E2E3E", tickfont={"color": MUTED},
                     fixedrange=True, showticklabels=not has_icons)
    fig.update_yaxes(gridcolor="#2E2E3E", zerolinecolor=MUTED, ticksuffix=" s",
                     tickfont={"color": MUTED}, fixedrange=True)
    fig.update_layout(
        title={"text": title, "font": {"size": 16, "color": TEXT}, "x": 0.02, "y": 0.95},
        font={"family": FONT, "color": TEXT}, paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 50, "r": 20, "t": 70, "b": 100 if has_icons else 20},
        bargap=0.4, hoverlabel={"bgcolor": PANEL, "font": {"family": FONT, "color": TEXT}})
    return fig


def _chart_card(title, note, fig, nav=True, graph_id=None):
    kw = {"id": graph_id} if graph_id else {}
    return html.Div(style=card, children=[
        html.H3(title, style={"marginTop": 0, "textTransform": "uppercase", "fontSize": "16px"}),
        html.Div(note, style={"color": MUTED, "fontSize": "12px", "marginBottom": "8px"}),
        dcc.Graph(figure=fig, className="bar-anim nav-chart" if nav else "",
                  config={"displayModeBar": False}, style={"height": "440px"}, **kw),
    ])


#Oszlopdiagram egységes formázása
def bar_fig(title, rounds, current, series, unit="", lap=False, reverse=False,
            fmt=None, yrange=None):
    names = [round_names[r] for r in rounds]
    ticktext = [f'<span style="color:{RED}"><b>{n}</b></span>' if r == current else n
                for r, n in zip(rounds, names)]
    fig = go.Figure()

    for i, (name, vals) in enumerate(series.items()):
        if fmt:
            hover = [fmt(v) for v in vals]
        else:
            hover = [fmt_lap(v) if lap else (f"{v:.1f}{unit}" if v is not None else "–")
                     for v in vals]
        fig.add_trace(go.Bar(
            x=names, y=vals, name=name, text=hover,
            hovertemplate="%{x}<br>" + name + ": %{text}<extra></extra>",
            marker={"color": SERIES_COLORS[i % len(SERIES_COLORS)]}))

    fig.update_xaxes(type="category", categoryorder="array", categoryarray=names,
                     tickmode="array", tickvals=names, ticktext=ticktext,
                     tickangle=-40, automargin=True,
                     tickfont={"size": 12, "color": MUTED},
                     showgrid=False, linecolor="#2E2E3E",
                     fixedrange=True)
    fig.update_yaxes(gridcolor="#2E2E3E", zerolinecolor="#2E2E3E", automargin=True,
                     ticksuffix="" if lap else unit,
                     title="s" if lap else None,
                     tickfont={"color": MUTED},
                     autorange="reversed" if reverse else True,
                     fixedrange=True)
    if yrange:                                   
        fig.update_yaxes(range=list(yrange), autorange=False)

    fig.update_layout(
        title={"text": title, "font": {"size": 16, "color": TEXT}, "x": 0.02, "y": 0.95},
        font={"family": FONT, "color": TEXT},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin={"l": 50, "r": 20, "t": 70, "b": 20},
        legend={"orientation": "h", "x": 1, "xanchor": "right", "y": 1.12,
                "yanchor": "bottom", "font": {"color": MUTED}},
        showlegend=len(series) > 1,
        barmode="group", bargap=0.25,
        hovermode="x unified",
        hoverlabel={"bgcolor": PANEL, "font": {"family": FONT, "color": TEXT}})
    return fig


def bar_chart(title, rounds, current, series, unit="", lap=False, reverse=False):
    fig = bar_fig(title, rounds, current, series, unit, lap, reverse)
    return html.Div(dcc.Graph(figure=fig, className="bar-anim nav-chart",
                              config={"displayModeBar": False},
                              style={"height": "440px"}), style=card)
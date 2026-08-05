"""Kairo Dashboard — JetBrains Mono, dark, data-dense, Mirofish-inspired."""

import streamlit as st
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
import time

BG = "#0a0b0f"
SURF = "#111318"
SURF2 = "#161920"
BORDER = "#1e2028"
TEXT = "#e3e5e8"
DIM = "#6b6e77"
GREEN = "#00e676"
RED = "#ff5252"
AMBER = "#ffb74d"
BLUE = "#64b5f6"
CYAN = "#4dd0e1"

API = "http://127.0.0.1:8000"


def _inject():
    st.markdown(f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&display=swap');

    * {{ font-family: 'JetBrains Mono', 'Cascadia Code', monospace !important; }}
    .stApp {{ background: {BG}; color: {TEXT}; }}
    section[data-testid="stSidebar"] {{
        background: {SURF}; border-right: 1px solid {BORDER};
    }}
    .stButton > button {{
        font-family: inherit; border-radius: 4px;
        border: 1px solid {BORDER}; font-size: 11px; padding: 8px 22px;
        background: {SURF}; color: {DIM}; font-weight: 600;
        letter-spacing: 0.5px; transition: all 0.2s ease;
    }}
    .stButton > button:hover {{ border-color: {TEXT}; color: {TEXT}; }}
    .metric-hero {{
        font-size: 56px; font-weight: 700; letter-spacing: -2px; line-height: 1;
    }}
    .metric-sub {{
        font-size: 11px; color: {DIM}; text-transform: uppercase;
        letter-spacing: 1px; font-weight: 500;
    }}
    .tag {{
        display: inline-block; padding: 3px 12px; border-radius: 3px;
        font-size: 10px; font-weight: 600; letter-spacing: 1px;
        border: 1px solid; text-transform: uppercase;
    }}
    .row {{
        display: flex; justify-content: space-between; align-items: center;
        padding: 5px 0; border-bottom: 1px solid {BORDER}; font-size: 12px;
    }}
    .row:last-child {{ border-bottom: none; }}
    .lev-track {{ background: {BORDER}; height: 3px; border-radius: 2px; }}
    .lev-fill {{ height: 3px; border-radius: 2px; transition: width 0.5s ease; }}
    hr {{ border-color: {BORDER}; margin: 6px 0; }}
    .sm {{ font-size: 11px; color: {DIM}; margin-bottom: 3px; }}
    .stCheckbox label {{ color: {DIM}; font-size: 12px; }}
    </style>
    """, unsafe_allow_html=True)


def _fetch(path: str) -> dict:
    try:
        import requests
        return requests.get(f"{API}{path}", timeout=3).json()
    except Exception:
        return {}


def _post(path: str, body: dict) -> dict:
    try:
        import requests
        return requests.post(f"{API}{path}", json=body, timeout=3).json()
    except Exception:
        return {}


def _fmt(v: float, p: str = "$") -> str:
    if abs(v) >= 1e6: return f"{p}{v/1e6:+,.2f}M"
    if abs(v) >= 1e3: return f"{p}{v:+,.0f}"
    return f"{p}{v:+,.2f}"


def _clr(v: float) -> str:
    return GREEN if v > 0 else RED if v < 0 else DIM


def _side_clr(s: str) -> str:
    return GREEN if s.upper() in ("LONG", "BUY") else RED


def render():
    st.set_page_config(page_title="Kairo", layout="wide", page_icon="◆")
    _inject()

    d = _fetch("/dashboard-data")
    fu = d.get("futures") or {}
    s = d.get("summary", {})

    mode = fu.get("mode", "vanilla")
    unlocked = fu.get("futures_unlocked", False)
    leverage = fu.get("leverage", 1.0)
    exec_path = fu.get("execution_path", "spot")
    checks = fu.get("checks", {})
    gate = fu
    dpnl = s.get("daily_pnl", 0)
    tpnl = s.get("total_pnl", 0)

    # ───── SIDEBAR ─────
    auto = st.sidebar.checkbox("Auto-refresh (3s)", value=True)
    st.sidebar.markdown(f"<span class='sm'>API: {API}</span>", unsafe_allow_html=True)
    st.sidebar.markdown("---")
    st.sidebar.markdown(f"<span class='sm'>RUNTIME PROFILE</span>", unsafe_allow_html=True)

    c1, c2 = st.sidebar.columns(2)
    with c1:
        if st.button("Vanilla", use_container_width=True,
                     type="primary" if mode == "vanilla" else "secondary"):
            _post("/mode", {"command": "vanilla"})
            st.rerun()
    with c2:
        if st.button("Aggressive", use_container_width=True,
                     type="primary" if mode == "aggressive" else "secondary"):
            _post("/mode", {"command": "aggressive"})
            st.rerun()

    st.sidebar.markdown("---")
    gate_icon = "\u25c6" if unlocked else "\u25c7"
    gate_color = GREEN if unlocked else AMBER
    st.sidebar.markdown(
        f"<span class='sm'>FUTURES GATE</span><br>"
        f"<span style='color:{gate_color};font-size:15px;font-weight:700'>{gate_icon} {'Unlocked' if unlocked else 'Locked'}</span>",
        unsafe_allow_html=True,
    )

    lev = max(1.0, min(2.0, leverage))
    lev_pct = (lev / 2.0) * 100
    lev_c = GREEN if lev > 1 else DIM
    st.sidebar.markdown(f"""
    <div style='display:flex;justify-content:space-between;margin:4px 0'>
        <span class='sm'>LEVERAGE</span>
        <span style='color:{lev_c};font-size:15px;font-weight:700'>{lev:.1f}x</span>
    </div>
    <div class='lev-track'><div class='lev-fill' style='width:{lev_pct}%;background:{lev_c}'></div></div>
    <div style='display:flex;justify-content:space-between;font-size:8px;color:{DIM}'>
        <span>1x</span><span>2x</span>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("---")
    for label, key in [("Min Trades (50)", "min_trades"), ("Sharpe >= 1.2", "sharpe"),
                        ("Win Rate >= 40%", "win_rate"), ("Profit Days >= 5", "profitable_days")]:
        ok = checks.get(key, False)
        ok_char = "\u2713" if ok else "\u2717"
        st.sidebar.markdown(
            f"<span style='color:{GREEN if ok else RED};font-size:11px'>{ok_char}</span> "
            f"<span style='font-size:11px;color:{DIM};margin-bottom:3px'>{label}</span>",
            unsafe_allow_html=True,
        )
    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<span style='color:{DIM};font-size:9px'>"
        f"PATH: {exec_path.upper()} | TRADES: {gate.get('total_spot_trades',0)}/50<br>"
        f"SHARPE: {gate.get('rolling_sharpe',0):.2f} | WR: {gate.get('win_rate',0):.1%}</span>",
        unsafe_allow_html=True,
    )

    # ───── HEADER ─────
    h1, h2, h3 = st.columns([2, 1, 1])
    with h1:
        st.markdown(f"<span style='font-size:22px;font-weight:700;color:{TEXT}'><span style='color:{GREEN}'>\u25c6</span> Kairo</span>", unsafe_allow_html=True)
    with h2:
        tag_c = GREEN if mode == "vanilla" else AMBER
        st.markdown(f"<div class='tag' style='border-color:{tag_c};color:{tag_c};margin-top:2px'>{mode}</div>", unsafe_allow_html=True)
    with h3:
        st.markdown(f"<span style='color:{DIM};font-size:12px;float:right;margin-top:4px'>{datetime.now():%H:%M:%S} IST</span>", unsafe_allow_html=True)

    # ───── HERO ─────
    hc1, hc2 = st.columns([1, 2])
    with hc1:
        st.markdown(f"""
        <div class='metric-hero' style='color:{_clr(dpnl)}'>{_fmt(dpnl)}</div>
        <div class='metric-sub'>P&amp;L Today &middot; {s.get('total_trades',0)} Trades &middot; {s.get('win_rate',0)}% WR</div>
        <div style='display:flex;gap:24px;margin-top:10px;font-size:12px;color:{DIM}'>
            <span>Bal {_fmt(s.get('balance',0))}</span>
            <span>{s.get('wins',0)}W / {s.get('losses',0)}L</span>
            <span>Total {_fmt(tpnl)}</span>
            <span>Uptime {s.get('uptime_hours',0):.1f}h</span>
        </div>
        """, unsafe_allow_html=True)

    with hc2:
        eq = d.get("equity_curve", [])
        if eq and len(eq) > 1:
            is_up = eq[-1] >= 5000
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=eq, mode="lines", fill="tozeroy",
                line={"color": GREEN if is_up else RED, "width": 2.5, "shape": "spline", "smoothing": 0.6},
                fillcolor="rgba(0,230,118,0.08)" if is_up else "rgba(255,82,82,0.08)",
            ))
            fig.update_layout(
                template="plotly_dark", height=130, margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor=SURF, plot_bgcolor=SURF,
                showlegend=False, xaxis=dict(showgrid=False, visible=False),
                yaxis=dict(showgrid=False, visible=False),
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

    st.markdown("<hr/>", unsafe_allow_html=True)

    # ───── MIDDLE: Lattice + Positions ─────
    ml1, ml2 = st.columns([2, 1])
    with ml1:
        st.markdown(f"<span style='color:{DIM};font-size:10px;text-transform:uppercase;letter-spacing:1px;font-weight:600'>Probability Lattice &middot; {s.get('total_trades',0)} Signals</span>", unsafe_allow_html=True)
        sc = d.get("signal_confidence", [])
        so = d.get("signal_outcome", [])
        if sc:
            wx, wy = [], []
            lx, ly = [], []
            for c, o in zip(sc, so):
                (wx if o else lx).append(c)
                (wy if o else ly).append(1 if o else 0)
            fig2 = go.Figure()
            if wx: fig2.add_trace(go.Scatter(x=wx, y=wy, mode="markers", name="Win", marker=dict(color=GREEN, size=9, symbol="circle", opacity=0.85)))
            if lx: fig2.add_trace(go.Scatter(x=lx, y=ly, mode="markers", name="Loss", marker=dict(color=RED, size=9, symbol="x-thin", opacity=0.75)))
            fig2.update_layout(
                template="plotly_dark", height=240, margin=dict(l=45, r=15, t=5, b=35),
                paper_bgcolor=SURF, plot_bgcolor=SURF,
                xaxis=dict(title="", range=[0.3, 1], showgrid=True, gridcolor=BORDER, color=DIM, tickformat=".0%"),
                yaxis=dict(tickvals=[0, 1], ticktext=["Loss", "Win"], range=[-0.2, 1.2], showgrid=True, gridcolor=BORDER, color=DIM),
                legend=dict(x=1, y=1, font=dict(color=DIM)),
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})
            st.markdown(f"<span style='color:{DIM};font-size:10px'>Bull: {len(wx) if sc else 0} | Avg Conf: {np.mean(sc) if sc else 0:.2f} | Bias: {'Bullish' if len(wx)>len(lx) else 'Bearish' if len(lx)>len(wx) else 'Neutral'}</span>", unsafe_allow_html=True)
        else:
            st.markdown(f"<span style='color:{DIM};font-size:12px'>No signal data yet</span>", unsafe_allow_html=True)

    with ml2:
        ps = d.get("positions", [])
        st.markdown(f"<span style='color:{DIM};font-size:10px;text-transform:uppercase;letter-spacing:1px;font-weight:600'>Open Positions &middot; {len(ps)}</span>", unsafe_allow_html=True)
        if ps:
            for p in ps:
                sym = (p.get("symbol","?") or "?").split("/")[0]
                side = p.get("side","?")
                sc = _side_clr(side)
                st.markdown(f"""
                <div class='row'>
                    <span style='color:{BLUE};font-weight:600'>{sym}</span>
                    <span style='color:{sc};font-weight:600'>{side.upper()}</span>
                    <span>$ {p.get('entry',0):.2f}</span>
                    <span style='color:{DIM}'>$ {p.get('value',0):.0f}</span>
                    <span style='color:{DIM};font-size:10px'>SL:{p.get('sl',0):.4f} TP:{p.get('tp',0):.4f}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"<span style='color:{DIM};font-size:12px'>No open positions</span>", unsafe_allow_html=True)

    st.markdown("<hr/>", unsafe_allow_html=True)

    # ───── BOTTOM: Trades + Distribution ─────
    bl1, bl2 = st.columns([1, 1])
    with bl1:
        st.markdown(f"<span style='color:{DIM};font-size:10px;text-transform:uppercase;letter-spacing:1px;font-weight:600'>Recent Trades</span>", unsafe_allow_html=True)
        ts = d.get("recent_trades", [])
        if ts:
            for t in ts[-8:]:
                sym = (t.get("symbol","?") or "?").split("/")[0]
                pnl = t.get("pnl", 0)
                pct = t.get("pnl_pct", 0)
                st.markdown(f"""
                <div class='row'>
                    <span style='color:{BLUE};font-weight:600'>{sym}</span>
                    <span style='font-size:10px'>{t.get('side','?')}</span>
                    <span style='color:{_clr(pnl)};font-weight:600'>{_fmt(pnl)} ({pct:.1f}%)</span>
                    <span style='color:{DIM};font-size:10px'>{t.get('reason','?')}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"<span style='color:{DIM};font-size:12px'>No trades yet</span>", unsafe_allow_html=True)

    with bl2:
        st.markdown(f"<span style='color:{DIM};font-size:10px;text-transform:uppercase;letter-spacing:1px;font-weight:600'>P&amp;L Distribution</span>", unsafe_allow_html=True)
        if ts:
            vals = [t.get("pnl", 0) for t in ts]
            fig3 = go.Figure()
            fig3.add_trace(go.Bar(x=vals, y=[1]*len(vals), type='histogram', nbinsx=20,
                                  marker=dict(color=[GREEN if v>=0 else RED for v in vals], opacity=0.8, line=dict(width=0))))
            fig3.update_layout(
                template="plotly_dark", height=240, margin=dict(l=45, r=15, t=5, b=25),
                paper_bgcolor=SURF, plot_bgcolor=SURF,
                showlegend=False, bargap=0.05,
                xaxis=dict(title="", showgrid=True, gridcolor=BORDER, color=DIM, tickprefix="$"),
                yaxis=dict(title="", showgrid=True, gridcolor=BORDER, color=DIM),
            )
            st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})
        else:
            st.markdown(f"<span style='color:{DIM};font-size:12px'>No trade data</span>", unsafe_allow_html=True)

    # ───── FOOTER ─────
    st.markdown(f"""
    <div style='position:fixed;bottom:0;left:0;right:0;background:{BG};border-top:1px solid {BORDER};
    padding:8px 24px;display:flex;justify-content:space-between;font-size:10px;color:{DIM};
    font-weight:600;text-transform:uppercase;letter-spacing:1px;z-index:999'>
        <span>&#9670; Kairo v0.3 &middot; {mode.upper()} &middot; LEV {lev:.1f}x &middot; {exec_path.upper()}</span>
        <span>{datetime.now().isoformat()}</span>
    </div>""", unsafe_allow_html=True)

    if auto:
        time.sleep(3)
        st.rerun()


if __name__ == "__main__":
    render()

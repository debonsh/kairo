import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import json
import time
from pathlib import Path

# --- 1. PAGE SETUP & NOTHING DOT-MATRIX CSS INJECTION ---
st.set_page_config(
    page_title="Kairo Quant Terminal",
    page_icon="⚫",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Inject Nothing Dot-Matrix Web Fonts and Pure Pitch-Black Styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=DotGothic16&family=Silkscreen&family=VT323&display=swap');

    /* PURE PITCH BLACK BACKGROUND - NO PURPLE/NAVY TINT */
    html, body, [class*="css"] {
        font-family: 'DotGothic16', 'VT323', monospace !important;
        background-color: #000000 !important;
        color: #E4E4E7 !important;
    }
    
    .stApp {
        background-color: #000000 !important;
    }
    
    /* HIDE STREAMLIT HEADER & FOOTER */
    header { visibility: hidden; }
    footer { visibility: hidden; }
    
    /* SIDEBAR PITCH BLACK OVERRIDE */
    section[data-testid="stSidebar"] {
        background-color: #050507 !important;
        border-right: 1px solid #18181B !important;
    }
    
    /* OBSIDIAN CARD CONTAINERS */
    .quant-card {
        background-color: #09090B;
        border: 1px solid #18181B;
        border-radius: 6px;
        padding: 16px;
        margin-bottom: 12px;
    }
    
    /* NOTHING DOT MATRIX LED METRIC READOUTS */
    .ndot-header {
        font-family: 'Silkscreen', 'DotGothic16', monospace !important;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    
    .ndot-number-green {
        font-family: 'VT323', 'DotGothic16', monospace !important;
        font-size: 3.2rem;
        font-weight: 700;
        line-height: 1.0;
        color: #00FF66;
        text-shadow: 0 0 12px rgba(0, 255, 102, 0.4);
    }
    
    .ndot-number-red {
        font-family: 'VT323', 'DotGothic16', monospace !important;
        font-size: 3.2rem;
        font-weight: 700;
        line-height: 1.0;
        color: #FF2E4D;
        text-shadow: 0 0 12px rgba(255, 46, 77, 0.4);
    }

    /* BADGES */
    .dot-badge {
        font-family: 'Silkscreen', monospace;
        background-color: #0F0F12;
        color: #00FF66;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.70rem;
        border: 1px solid #00FF66;
        display: inline-block;
    }
    
    .dot-badge-vanilla {
        font-family: 'Silkscreen', monospace;
        background-color: #0F0F12;
        color: #A1A1AA;
        padding: 4px 10px;
        border-radius: 4px;
        font-size: 0.70rem;
        border: 1px solid #3F3F46;
        display: inline-block;
    }

    /* FIX BUTTON WRAPPING & UGLY RED BUTTONS */
    div.stButton > button {
        font-family: 'Silkscreen', monospace !important;
        white-space: nowrap !important;
        width: 100% !important;
        background-color: #09090B !important;
        color: #A1A1AA !important;
        border: 1px solid #27272A !important;
        padding: 8px 16px !important;
        border-radius: 4px !important;
        transition: all 0.2s ease !important;
    }
    
    div.stButton > button:hover {
        border-color: #00FF66 !important;
        color: #00FF66 !important;
        box-shadow: 0 0 10px rgba(0, 255, 102, 0.2);
    }

    .stat-label {
        font-family: 'Silkscreen', monospace;
        font-size: 0.68rem;
        color: #71717A;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    .stat-value {
        font-size: 1.1rem;
        color: #FAFAFA;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. PLOTLY PITCH-BLACK THEME CONFIGURATION ---
PLOT_BG = "#000000"
PAPER_BG = "#000000"
GRID_COLOR = "#121215"

# --- 3. STATE MANAGEMENT ---
STATE_FILE = Path("data/runtime_state.json")

def load_mode():
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f).get("mode", "vanilla")
        except Exception:
            pass
    return "vanilla"

def save_mode(mode: str):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump({"mode": mode, "last_updated": time.time()}, f, indent=2)

current_mode = load_mode()

# --- 4. SIDEBAR ENGINE CONTROLS ---
st.sidebar.markdown('<div class="ndot-header" style="font-size:1.1rem; color:#FAFAFA; margin-bottom:12px;">● KAIRO CONTROL</div>', unsafe_allow_html=True)

st.sidebar.markdown('<div class="stat-label">SELECT EXECUTION MODE</div>', unsafe_allow_html=True)
col_v, col_a = st.sidebar.columns(2)

with col_v:
    if st.button("VANILLA", key="btn_vanilla"):
        save_mode("vanilla")
        st.rerun()

with col_a:
    if st.button("AGGRESSIVE", key="btn_aggr"):
        save_mode("aggressive")
        st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(f'<div class="stat-label">ACTIVE MODE</div><div style="font-size:1.2rem; font-weight:700; color:{"#00FF66" if current_mode=="aggressive" else "#A1A1AA"};">{current_mode.upper()}</div>', unsafe_allow_html=True)

st.sidebar.markdown("---")
st.sidebar.markdown('<div class="stat-label">TELEMETRY</div>', unsafe_allow_html=True)
st.sidebar.markdown("🟢 **Tick Stream:** Connected")
st.sidebar.markdown("🟢 **LLM Engine:** Qwen3:8b")
st.sidebar.markdown("🟢 **Latency:** 18ms")

# --- 5. PLOTLY VISUALIZERS ---

def build_probability_lattice():
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.65, 0.35])
    np.random.seed(42)
    n_balls = 70
    returns = np.random.normal(0.002, 0.012, n_balls)
    balls_y = np.random.uniform(0.1, 1.0, n_balls)
    colors = ['#00FF66' if r > 0 else '#FF2E4D' for r in returns]
    
    fig.add_trace(go.Scatter(
        x=returns * 100, y=balls_y, mode='markers',
        marker=dict(size=8, color=colors, opacity=0.9, line=dict(width=1, color='#FFFFFF')),
        showlegend=False
    ), row=1, col=1)
    
    fig.add_trace(go.Histogram(
        x=returns * 100, marker=dict(color='#00FF66', line=dict(color='#000000', width=1)),
        nbinsx=18, showlegend=False
    ), row=2, col=1)
    
    fig.add_vline(x=0, line_dash="dash", line_color="#3F3F46", row="all", col=1)
    fig.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        margin=dict(l=10, r=10, t=10, b=10), height=240,
        font=dict(family="DotGothic16", color="#A1A1AA", size=11)
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=GRID_COLOR, zeroline=False)
    return fig

def build_ridgeline_landscape():
    fig = go.Figure()
    np.random.seed(101)
    x_axis = np.linspace(-4, 8, 200)
    for i in range(5):
        mean = 0.4 + (i * 0.3)
        std = 1.0 + (i * 0.1)
        density = (1 / (std * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x_axis - mean) / std) ** 2)
        y_offset = density + (i * 0.25)
        fig.add_trace(go.Scatter(
            x=x_axis, y=y_offset, mode='lines',
            line=dict(color='#00FF66' if i >= 2 else '#3F3F46', width=1.5),
            fill='tonexty' if i > 0 else 'none',
            fillcolor=f'rgba(0, 255, 102, {0.06 * i})',
            showlegend=False
        ))
    fig.add_vline(x=3.0, line_dash="solid", line_color="#FF2E4D", annotation_text="3.0x ATR STRIKE", annotation_position="top right")
    fig.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        margin=dict(l=10, r=10, t=10, b=10), height=240,
        font=dict(family="DotGothic16", color="#A1A1AA", size=11)
    )
    fig.update_xaxes(showgrid=True, gridcolor=GRID_COLOR, title="ATR Return Multiplier")
    fig.update_yaxes(showgrid=False, showticklabels=False)
    return fig

def build_network_graph():
    nodes = {
        "HUB_PRIME": (0, 0, "#FAFAFA", 24),
        "BEAR_CLUSTER": (-2, 1, "#FF2E4D", 18),
        "CATALYST_RING": (1.5, 0.8, "#A1A1AA", 14),
        "BULL_SIGNAL": (1, -1.2, "#00FF66", 16),
    }
    edge_x, edge_y = [], []
    for name, (x, y, c, s) in nodes.items():
        if name != "HUB_PRIME":
            edge_x.extend([0, x, None])
            edge_y.extend([0, y, None])

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=edge_x, y=edge_y, line=dict(width=1, color='#27272A'), hoverinfo='none', mode='lines', showlegend=False))
    for name, (x, y, color, size) in nodes.items():
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode='markers+text', text=[name], textposition="bottom center",
            marker=dict(size=size, color=color, line=dict(width=2, color='#000000')),
            showlegend=False
        ))
    fig.update_layout(
        paper_bgcolor=PAPER_BG, plot_bgcolor=PLOT_BG,
        margin=dict(l=10, r=10, t=10, b=10), height=230,
        font=dict(family="DotGothic16", color="#A1A1AA", size=10)
    )
    fig.update_xaxes(showgrid=False, zeroline=False, showticklabels=False)
    fig.update_yaxes(showgrid=False, zeroline=False, showticklabels=False)
    return fig

# --- 6. HEADER ROW ---
top_l, top_r = st.columns([3, 1])
with top_l:
    st.markdown(f"""
        <div style="display: flex; align-items: center; gap: 14px; margin-bottom: 8px;">
            <span class="ndot-header" style="font-size: 1.6rem; font-weight: 800; color: #FAFAFA;">KAIRO QUANT TERMINAL</span>
            <span class="{'dot-badge' if current_mode=='aggressive' else 'dot-badge-vanilla'}">{current_mode.upper()} MODE</span>
            <span style="color: #52525B; font-size: 0.85rem; font-family: 'Silkscreen';">ROUND #8412 • 08:06:12 IST</span>
        </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# --- 7. HERO P&L LEDGER CARD ---
st.markdown('<div class="quant-card">', unsafe_allow_html=True)
h1, h2, h3 = st.columns([1.5, 2, 1.5])

with h1:
    st.markdown('<div class="stat-label">TOTAL REALIZED P&L</div>', unsafe_allow_html=True)
    st.markdown('<div class="ndot-number-green">$401,918</div>', unsafe_allow_html=True)
    st.markdown('<span style="color: #00FF66;">▲ +18.4% MONTH</span> | <span style="color: #71717A;">5,944 TRADES</span>', unsafe_allow_html=True)

with h2:
    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.markdown('<div class="stat-label">WIN RATE</div><div class="stat-value" style="color:#00FF66;">71.4%</div>', unsafe_allow_html=True)
        st.markdown('<div class="stat-label" style="margin-top:8px;">SHARPE RATIO</div><div class="stat-value">4.21</div>', unsafe_allow_html=True)
    with mc2:
        st.markdown('<div class="stat-label">EXPECTED VAL</div><div class="stat-value">+$80 / trade</div>', unsafe_allow_html=True)
        st.markdown('<div class="stat-label" style="margin-top:8px;">ACTIVE LEVERAGE</div><div class="stat-value">2.0x (Perp)</div>', unsafe_allow_html=True)
    with mc3:
        st.markdown('<div class="stat-label">SESSION P&L</div><div class="stat-value" style="color:#00FF66;">+$29,247</div>', unsafe_allow_html=True)
        st.markdown('<div class="stat-label" style="margin-top:8px;">MAX DRAWDOWN</div><div class="stat-value" style="color:#FF2E4D;">-2.1%</div>', unsafe_allow_html=True)

with h3:
    st.markdown('<div class="stat-label">TOP TRADE TAIL SNIPER</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 1.6rem; font-weight:700; color:#00FF66; font-family:\'VT323\';">x12.75 <span style="font-size:1rem; color:#FAFAFA;">(+$28,062)</span></div>', unsafe_allow_html=True)
    st.caption("BTC/USDT Entry: $91,300 ➔ Payout: $119,362")

st.markdown('</div>', unsafe_allow_html=True)

# --- 8. MIDDLE ROW: PROBABILITY & TAIL LANDSCAPE ---
m_left, m_right = st.columns(2)

with m_left:
    st.markdown('<div class="quant-card">', unsafe_allow_html=True)
    st.markdown('<div class="stat-label">PROBABILITY LATTICE — 5,944 TRADES CONVERGENCE</div>', unsafe_allow_html=True)
    st.plotly_chart(build_probability_lattice(), use_container_width=True, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)

with m_right:
    st.markdown('<div class="quant-card">', unsafe_allow_html=True)
    st.markdown('<div class="stat-label">TAIL PROBABILITY RIDGE — STRIKE LANDSCAPE</div>', unsafe_allow_html=True)
    st.plotly_chart(build_ridgeline_landscape(), use_container_width=True, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)

# --- 9. BOTTOM ROW: NETWORK GRAPH & EMERGENT PROBABILITY ---
b_left, b_right = st.columns([1.8, 1])

with b_left:
    st.markdown('<div class="quant-card">', unsafe_allow_html=True)
    st.markdown('<div class="stat-label">RELATIONSHIP GRAPH SIMULATION — SIGNAL CLUSTERS</div>', unsafe_allow_html=True)
    st.plotly_chart(build_network_graph(), use_container_width=True, config={'displayModeBar': False})
    st.markdown('</div>', unsafe_allow_html=True)

with b_right:
    st.markdown('<div class="quant-card" style="height: 275px;">', unsafe_allow_html=True)
    st.markdown('<div class="stat-label">EMERGENT PROBABILITY READOUT</div>', unsafe_allow_html=True)
    st.markdown('<div style="margin-top: 15px;">', unsafe_allow_html=True)
    st.markdown('<span class="stat-label">P(UP DIRECTION)</span> <span style="float:right; color:#00FF66; font-weight:700;">0.72</span>', unsafe_allow_html=True)
    st.progress(0.72)
    st.markdown('<span class="stat-label">P(DOWN DIRECTION)</span> <span style="float:right; color:#FF2E4D; font-weight:700;">0.28</span>', unsafe_allow_html=True)
    st.progress(0.28)
    st.markdown('<br><div class="stat-label">META-LABEL CONFIDENCE</div><div style="font-size:2rem; font-weight:800; color:#00FF66; font-family:\'VT323\';">90.6%</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# --- FOOTER ---
st.caption("❖ KAIRO ARCHITECTURE • RUNTIME STATE: CONNECTED • MODEL: QWEN3:8B LOCAL • REFRESH: 1S")

"""
Jinada.Trade — Modern Dark UI
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import time
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent))

from config import config
from database import get_db, init_database

init_database()

# ================================================================
st.set_page_config(
    page_title="Jinada.Trade | AI Trading",
    page_icon="🟡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# ================================================================
# MODERN DARK CSS
# ================================================================
st.markdown("""
<style>
    /* Import fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
    
    /* Global */
    * { font-family: 'Inter', sans-serif; }
    
    .stApp {
        background: #0D0D0D;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #111111;
        border-right: 1px solid #222222;
    }
    
    /* Main content */
    .main .block-container {
        padding-top: 1rem;
        max-width: 1400px;
    }
    
    /* Headers */
    h1 { color: #FFFFFF !important; font-weight: 700 !important; font-size: 2rem !important; }
    h2 { color: #FFFFFF !important; font-weight: 600 !important; font-size: 1.3rem !important; }
    h3 { color: #AAAAAA !important; font-weight: 500 !important; font-size: 1rem !important; }
    
    /* Cards */
    .metric-card {
        background: #141414;
        border: 1px solid #222222;
        border-radius: 12px;
        padding: 20px;
        transition: all 0.2s;
    }
    .metric-card:hover {
        border-color: #333333;
        background: #181818;
    }
    
    /* Metric value */
    [data-testid="stMetricValue"] {
        color: #FFFFFF !important;
        font-size: 28px !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 14px !important;
    }
    
    /* Buttons */
    .stButton > button {
        background: #FFFFFF;
        color: #000000;
        border: none;
        border-radius: 8px;
        padding: 10px 20px;
        font-weight: 600;
        font-size: 14px;
        transition: all 0.2s;
    }
    .stButton > button:hover {
        background: #E5E5E5;
        transform: translateY(-1px);
    }
    
    /* Secondary button */
    .stButton > button[kind="secondary"] {
        background: #1A1A1A;
        color: #FFFFFF;
        border: 1px solid #333333;
    }
    .stButton > button[kind="secondary"]:hover {
        background: #222222;
        border-color: #444444;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 5px;
        background: transparent;
        border-bottom: 1px solid #222222;
    }
    .stTabs [data-baseweb="tab"] {
        color: #666666;
        background: transparent;
        border: none;
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
        font-weight: 500;
        font-size: 14px;
    }
    .stTabs [aria-selected="true"] {
        color: #FFFFFF;
        background: #1A1A1A;
        border-bottom: 2px solid #FFFFFF;
    }
    
    /* Dataframe */
    .stDataFrame {
        background: #141414;
        border: 1px solid #222222;
        border-radius: 12px;
    }
    .stDataFrame table {
        background: transparent;
    }
    .stDataFrame th {
        background: #1A1A1A !important;
        color: #888888 !important;
        font-weight: 500 !important;
        font-size: 12px !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .stDataFrame td {
        background: transparent !important;
        color: #CCCCCC !important;
        font-size: 13px !important;
    }
    
    /* Info/Success/Warning boxes */
    .stAlert {
        background: #141414;
        border: 1px solid #222222;
        border-radius: 10px;
        color: #CCCCCC;
    }
    
    /* Slider */
    .stSlider > div > div > div { background: #333333; }
    .stSlider > div > div > div > div { background: #FFFFFF; }
    
    /* Select box */
    .stSelectbox > div > div {
        background: #141414;
        border: 1px solid #222222;
        border-radius: 8px;
        color: #FFFFFF;
    }
    
    /* Divider */
    hr {
        border-color: #222222 !important;
        margin: 0.5rem 0 !important;
    }
    
    /* Captions */
    .caption {
        color: #666666;
        font-size: 12px;
    }
    
    /* Status dot */
    .status-dot {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        margin-right: 8px;
    }
    .status-dot.green { background: #00FF88; }
    .status-dot.yellow { background: #FFD700; }
    .status-dot.red { background: #FF4444; }
    
    /* Position card */
    .position-card {
        background: #141414;
        border: 1px solid #222222;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 10px;
    }
    .position-card:hover {
        border-color: #333333;
    }
    
    /* Badge */
    .badge {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .badge.green { background: rgba(0,255,136,0.1); color: #00FF88; }
    .badge.red { background: rgba(255,68,68,0.1); color: #FF4444; }
    .badge.neutral { background: rgba(255,215,0,0.1); color: #FFD700; }
    
    /* Chart container */
    .chart-container {
        background: #141414;
        border: 1px solid #222222;
        border-radius: 12px;
        padding: 16px;
    }
</style>
""", unsafe_allow_html=True)

# ================================================================
# DATA FUNCTIONS
# ================================================================
def load_stats():
    with get_db() as db:
        total = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED'").fetchone()[0]
        wins = db.execute("SELECT COUNT(*) FROM trades WHERE status='CLOSED' AND pnl>0").fetchone()[0]
        pnl = db.execute("SELECT SUM(pnl) FROM trades WHERE status='CLOSED'").fetchone()[0] or 0
        today = db.execute("SELECT COUNT(*), SUM(pnl) FROM trades WHERE status='CLOSED' AND date(exit_time)=date('now')").fetchone()
        open_pos = db.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0]
    return {
        'total': total, 'wins': wins, 'pnl': pnl,
        'today_trades': today[0] or 0, 'today_pnl': today[1] or 0,
        'open_positions': open_pos,
        'winrate': (wins/total*100) if total > 0 else 0
    }

def load_balance():
    try:
        with open("balance.txt", "r") as f:
            return float(f.read().strip())
    except:
        return config.INITIAL_BALANCE

def load_positions():
    with get_db() as db:
        return db.execute("""
            SELECT symbol, direction, entry_price, quantity, stop_loss, take_profit, entry_time
            FROM trades WHERE status='OPEN'
        """).fetchall()

def load_trades(limit=30):
    with get_db() as db:
        return db.execute(f"""
            SELECT symbol, direction, entry_price, exit_price, pnl, exit_reason, strategy, exit_time
            FROM trades WHERE status='CLOSED'
            ORDER BY exit_time DESC LIMIT {limit}
        """).fetchall()

def load_daily_pnl():
    with get_db() as db:
        return db.execute("""
            SELECT date(exit_time) as day, SUM(pnl) as pnl, COUNT(*) as trades
            FROM trades WHERE status='CLOSED'
            GROUP BY day ORDER BY day DESC LIMIT 14
        """).fetchall()

# ================================================================
stats = load_stats()
balance = load_balance()
positions = load_positions()
trades = load_trades(30)
daily = load_daily_pnl()

# ================================================================
# TOP BAR
# ================================================================
col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])

with col1:
    st.markdown("""
    <div style="display: flex; align-items: center; gap: 12px;">
        <div class="status-dot green"></div>
        <span style="color: #FFFFFF; font-size: 18px; font-weight: 700;">Jinada.Trade</span>
        <span class="badge neutral">BETA</span>
    </div>
    """, unsafe_allow_html=True)

with col2:
    initial = config.INITIAL_BALANCE
    change = ((balance - initial) / initial * 100) if initial > 0 else 0
    delta_color = "normal" if change >= 0 else "inverse"
    st.metric("Balance", f"${balance:.0f}", f"{change:+.1f}%", delta_color=delta_color)

with col3:
    st.metric("PnL", f"${stats['pnl']:+.0f}")

with col4:
    st.metric("Winrate", f"{stats['winrate']:.0f}%" if stats['total'] > 0 else "—")

with col5:
    st.metric("Today", f"${stats['today_pnl']:+.0f}" if stats['today_pnl'] != 0 else "$0")

st.markdown("<hr>", unsafe_allow_html=True)

# ================================================================
# TABS
# ================================================================
tab1, tab2, tab3 = st.tabs(["Overview", "Positions", "History"])

# ================================================================
# TAB 1: OVERVIEW
# ================================================================
with tab1:
    col_left, col_right = st.columns([2.5, 1])
    
    with col_left:
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("#### Balance Evolution")
        
        if daily:
            days = [d['day'] for d in reversed(daily)]
            pnls = [d['pnl'] or 0 for d in reversed(daily)]
            cumulative = []
            cum = config.INITIAL_BALANCE
            for p in pnls:
                cum += p
                cumulative.append(cum)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=days, y=cumulative,
                mode='lines',
                line=dict(color='#FFFFFF', width=2),
                fill='tozeroy',
                fillcolor='rgba(255,255,255,0.03)',
                hovertemplate='%{y:.2f}$<extra></extra>'
            ))
            fig.update_layout(
                template='plotly_dark',
                height=350,
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                xaxis=dict(showgrid=False, color='#666666', showline=False),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color='#666666', showline=False),
                hovermode='x unified'
            )
            st.plotly_chart(fig, config={'displayModeBar': False}, width='stretch')
        else:
            st.info("Start trading to see the chart")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Recent PnL bars
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown('<div class="chart-container">', unsafe_allow_html=True)
        st.markdown("#### Recent Trades PnL")
        
        if trades:
            recent = list(reversed(trades[-15:]))
            pnls_list = [t['pnl'] or 0 for t in recent]
            symbols = [t['symbol'] for t in recent]
            colors = ['#00FF88' if p > 0 else '#FF4444' for p in pnls_list]
            
            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=symbols, y=pnls_list,
                marker_color=colors,
                text=[f'{p:+.2f}$' for p in pnls_list],
                textposition='outside',
                textfont=dict(color='#888888', size=11),
                hovertemplate='%{x}: %{y:.2f}$<extra></extra>'
            ))
            fig2.update_layout(
                template='plotly_dark',
                height=250,
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                showlegend=False,
                xaxis=dict(showgrid=False, color='#666666'),
                yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.05)', color='#666666')
            )
            st.plotly_chart(fig2, config={'displayModeBar': False}, width='stretch')
        
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col_right:
        st.markdown("#### Stats")
        st.markdown(f"""
        <div class="metric-card">
            <div style="color: #888; font-size: 12px; margin-bottom: 4px;">Total Trades</div>
            <div style="color: #FFF; font-size: 28px; font-weight: 700;">{stats['total']}</div>
        </div>
        <br>
        <div class="metric-card">
            <div style="color: #888; font-size: 12px; margin-bottom: 4px;">Winrate</div>
            <div style="color: #FFF; font-size: 28px; font-weight: 700;">{stats['winrate']:.1f}%</div>
        </div>
        <br>
        <div class="metric-card">
            <div style="color: #888; font-size: 12px; margin-bottom: 4px;">Open Positions</div>
            <div style="color: #FFF; font-size: 28px; font-weight: 700;">{stats['open_positions']}</div>
        </div>
        <br>
        <div class="metric-card">
            <div style="color: #888; font-size: 12px; margin-bottom: 4px;">Today</div>
            <div style="color: #FFF; font-size: 28px; font-weight: 700;">{stats['today_trades']} trades</div>
            <div style="color: {'#00FF88' if stats['today_pnl'] > 0 else '#FF4444'}; font-size: 16px;">{stats['today_pnl']:+.2f}$</div>
        </div>
        """, unsafe_allow_html=True)
        
        # Daily breakdown
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### Last 7 Days")
        for d in daily[:7]:
            pnl = d['pnl'] or 0
            color = '#00FF88' if pnl > 0 else '#FF4444'
            st.markdown(f"""
            <div style="display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #1A1A1A;">
                <span style="color: #888;">{d['day']}</span>
                <span style="color: {color}; font-weight: 600;">{pnl:+.2f}$</span>
            </div>
            """, unsafe_allow_html=True)

# ================================================================
# TAB 2: POSITIONS
# ================================================================
with tab2:
    if positions:
        for pos in positions:
            mock_prices = {"BTCUSDT": 73732, "ETHUSDT": 2016, "SOLUSDT": 82.56, "XRPUSDT": 0.6234, "DOGEUSDT": 0.0997, "UNIUSDT": 3.013}
            current = mock_prices.get(pos['symbol'], pos['entry_price'])
            
            if pos['direction'] == 'LONG':
                pnl = (current - pos['entry_price']) * (pos['quantity'] or 0)
                pnl_pct = (current - pos['entry_price']) / pos['entry_price'] * 100
            else:
                pnl = (pos['entry_price'] - current) * (pos['quantity'] or 0)
                pnl_pct = (pos['entry_price'] - current) / pos['entry_price'] * 100
            
            pnl_color = '#00FF88' if pnl > 0 else '#FF4444'
            
            st.markdown(f"""
            <div class="position-card">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <span style="color: #FFF; font-weight: 600; font-size: 16px;">{pos['symbol']}</span>
                        <span class="badge {'green' if pos['direction']=='LONG' else 'red'}" style="margin-left: 10px;">{pos['direction']}</span>
                    </div>
                    <div style="text-align: right;">
                        <span style="color: {pnl_color}; font-weight: 700; font-size: 18px;">{pnl:+.2f}$</span>
                        <span style="color: {pnl_color}; font-size: 13px; margin-left: 5px;">({pnl_pct:+.2f}%)</span>
                    </div>
                </div>
                <div style="display: flex; gap: 30px; margin-top: 12px; color: #888; font-size: 13px;">
                    <span>Entry: ${pos['entry_price']}</span>
                    <span>Current: ${current}</span>
                    <span>SL: {pos['stop_loss']}</span>
                    <span>TP: {pos['take_profit']}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No open positions")

# ================================================================
# TAB 3: HISTORY
# ================================================================
with tab3:
    if trades:
        data = []
        for t in trades:
            pnl = t['pnl'] or 0
            data.append({
                "TIME": t['exit_time'][:16] if t['exit_time'] else '-',
                "PAIR": t['symbol'],
                "TYPE": t['direction'],
                "ENTRY": f"${t['entry_price']}",
                "EXIT": f"${t['exit_price']}" if t['exit_price'] else '-',
                "PNL": f"{pnl:+.2f}$",
                "STRATEGY": t['strategy'] or '-'
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, width='stretch', hide_index=True)
        
        csv = df.to_csv(index=False)
        st.download_button("Download CSV", csv, f"jinada_{datetime.now().strftime('%Y%m%d')}.csv")
    else:
        st.info("No trades yet")

# ================================================================
# FOOTER
# ================================================================
st.markdown("<br><hr>", unsafe_allow_html=True)
st.markdown(f"""
<div style="display: flex; justify-content: space-between; color: #444; font-size: 12px;">
    <span>Jinada.Trade v4.0</span>
    <span>{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</span>
    <span>AI Trading Platform</span>
</div>
""", unsafe_allow_html=True)

time.sleep(5)
st.rerun()
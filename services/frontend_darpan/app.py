import streamlit as st
import requests
import pandas as pd
import os

# Configure Page
st.set_page_config(
    page_title="Project Gyan | Pro Investment System",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# API URL
API_URL = "http://setu_api:8000"

# --- CUSTOM CSS ---
st.markdown("""
<style>
    .stApp { background-color: #0E1117; }
    .card { background-color: #1E1E1E; padding: 20px; border-radius: 10px; border: 1px solid #333; margin-bottom: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }
    .card-title { font-size: 16px; color: #888; margin-bottom: 5px; font-weight: 600;}
    .verdict-text { font-size: 28px; font-weight: 800; margin-bottom: 15px; }
    .buy { color: #00C853; }
    .sell { color: #D50000; }
    .hold { color: #FFD600; }
    .waiting { color: #29B6F6; animation: blinker 1.5s linear infinite; }
    @keyframes blinker { 50% { opacity: 0.5; } }
    
    .metric-row { display: flex; justify-content: space-between; margin-top: 10px; }
    .metric-label { font-size: 13px; color: #aaa; }
    .metric-val { font-size: 16px; font-weight: bold; color: #fff; }
    .reasoning-box { background-color: #262730; padding: 15px; border-left: 5px solid #4CAF50; margin-top: 20px; border-radius: 5px; }
    
    .top-pick-card { border: 1px solid #444; border-radius: 8px; padding: 15px; background: #222; text-align: center; }
    .top-pick-rank { font-size: 12px; font-weight: bold; text-transform: uppercase; color: #FFD700; margin-bottom: 5px; }
    .top-pick-ticker { font-size: 24px; font-weight: bold; color: #fff; }
    .top-pick-upside { font-size: 18px; color: #00C853; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.title("🔮 Project Gyan: AI Investment System")

def safe_format(value, fmt="{:.2f}", default="N/A"):
    if value is None: return default
    if value == 0.0: return "---"
    return fmt.format(value)

    # Timeframe Colors
    st.markdown("""
    <style>
        .card-short { border-left: 5px solid #29B6F6; }
        .card-mid { border-left: 5px solid #FFD600; }
        .card-long { border-left: 5px solid #00C853; }
        .risk-badge { padding: 5px 10px; border-radius: 5px; font-weight: bold; color: #fff; display: inline-block; font-size: 12px; }
        .risk-low { background-color: #00C853; }
        .risk-medium { background-color: #FFA726; }
        .risk-high { background-color: #D50000; }
    </style>
    """, unsafe_allow_html=True)
    
def display_horizon_card(title, data, term_class):
    if data is None: return
    if isinstance(data, (dict, list)) and not data: return
    
    verdict = data.get('verdict', 'N/A')
    
    color_class = "hold"
    if verdict in ["BUY", "STRONG BUY"]: color_class = "buy"
    elif verdict == "SELL": color_class = "sell"
    elif verdict == "WAITING": color_class = "waiting"
    elif verdict == "ACCUMULATE": color_class = "buy"
    
    target = data.get('target')
    target_agg = data.get('target_agg', target) # Fallback
    sl = data.get('sl')
    rr = data.get('rr', 'N/A')
    
    st.markdown(f"""
    <div class="card {term_class}">
        <div class="card-title">{title}</div>
        <div class="verdict-text {color_class}">{verdict}</div>
        <div class="metric-row">
            <div>
                <div class="metric-label" title="Conservative Target">Target 1</div>
                <div class="metric-val">₹{safe_format(target)}</div>
            </div>
            <div style="text-align: right;">
                <div class="metric-label" title="Aggressive Target">Target 2</div>
                <div class="metric-val">₹{safe_format(target_agg)}</div>
            </div>
        </div>
        <div class="metric-row">
            <div>
                <div class="metric-label" title="Stop Loss Level">Stop Loss</div>
                <div class="metric-val" style="color: #ff6b6b;">₹{safe_format(sl)}</div>
            </div>
            <div style="text-align: right;">
                <div class="metric-label" title="Risk to Reward Ratio">Risk:Reward</div>
                <div class="metric-val" style="color: #4db6ac;">{rr}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def display_top_pick(rank, data, label="Top Pick"):
    if data is None: return
    if isinstance(data, pd.Series) and data.empty: return
    if isinstance(data, (dict, list)) and not data: return

    upside = data.get('upside_pct', 0)
    conf = data.get('confidence', 0) * 100
    ticker = data.get('ticker')
    
    rank_color = "#FFD700" if rank == 1 else "#C0C0C0" if rank == 2 else "#CD7F32"
    rank_text = "🥇 1st Choice" if rank == 1 else "🥈 2nd Choice" if rank == 2 else "🥉 3rd Choice"
    
    st.markdown(f"""
    <div class="top-pick-card" style="border-top: 3px solid {rank_color};">
        <div class="top-pick-rank" style="color: {rank_color};">{rank_text}</div>
        <div class="top-pick-ticker">{ticker}</div>
        <div class="top-pick-upside">+{upside:.1f}% Upside</div>
        <div style="font-size:12px; color:#888; margin-top:5px;">AI Confidence: {conf:.0f}%</div>
    </div>
    """, unsafe_allow_html=True)

# --- MAIN INTERFACE: DEEP ANALYSIS ---

# --- SESSION STATE MANAGEMENT ---
if "analysis_data" not in st.session_state:
    st.session_state["analysis_data"] = None
    
if "current_ticker" not in st.session_state:
    st.session_state["current_ticker"] = "RELIANCE.NS"

col1, col2 = st.columns([3, 1])
with col1:
    ticker_input = st.text_input("Enter Ticker (e.g. RELIANCE.NS)", value=st.session_state["current_ticker"])
with col2:
    st.write("")
    st.write("")
    analyze_btn = st.button("Analyze Stock", use_container_width=True, type="primary")

# Trigger Analysis
if analyze_btn:
    st.session_state["current_ticker"] = ticker_input
    with st.spinner(f"Analyzing {ticker_input}..."):
        try:
            res = requests.get(f"{API_URL}/analysis/{ticker_input}")
            if res.status_code == 200:
                st.session_state["analysis_data"] = res.json()
            else:
                st.error(f"Error: {res.text}")
                st.session_state["analysis_data"] = None
        except Exception as e:
            st.error(f"Connection Error: {e}")
            st.session_state["analysis_data"] = None

# Render Interface if Data Exists
if st.session_state["analysis_data"]:
    data = st.session_state["analysis_data"]
    
    # Market Status Logic
    import datetime
    import pytz
    
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.datetime.now(ist)
    market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
    
    is_market_open = (now.weekday() < 5) and (market_open <= now <= market_close)
    status_text = "🟢 OPEN" if is_market_open else "🔴 CLOSED"
    
    st.subheader(f"{data.get('company_name', ticker_input)}  {status_text}")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Current Price", f"₹{safe_format(data.get('current_price'))}")
    
    # Risk Badge
    risk_lvl = data.get('risk_level', 'MEDIUM')
    risk_cls = f"risk-{risk_lvl.lower()}"
    m2.markdown(f"**Risk Level**<br><span class='risk-badge {risk_cls}'>{risk_lvl}</span>", unsafe_allow_html=True)
    
    # Confidence
    conf = data.get('confidence', 0) * 100
    m3.metric("AI Confidence", f"{conf:.0f}%")
    
    # Updated Time
    upd = data.get('last_updated', 'Today')
    m4.metric("Last Updated", str(upd))
    
    st.divider()
    c1, c2, c3 = st.columns(3)
    with c1: display_horizon_card("Short Term (2 Weeks)", data.get('st', {}), "card-short")
    with c2: display_horizon_card("Mid Term (2 Months)", data.get('mt', {}), "card-mid")
    with c3: display_horizon_card("Long Term (1 Year)", data.get('lt', {}), "card-long")
    
    st.markdown(f"""
    <div class="reasoning-box">
        <strong>🤖 AI Reasoning:</strong><br>
        {data.get('reasoning', 'No reasoning available.').replace(chr(10), '<br>')}
    </div>
    <div style="margin-top: 10px; font-size: 12px; color: #666; text-align: center;">
        ⚠️ <strong>DISCLAIMER:</strong> This analysis is for educational purposes only. Not financial advice. 
        Markets are subject to risk. Please consult a SEBI registered advisor before trading.
    </div>
    """, unsafe_allow_html=True)
    
    # --- BACKTEST SECTION (Phase 4) ---
    st.write("")
    st.divider()
    st.subheader("🛠️ Strategy Validation (Beta)")
    
    if st.button("Run 3-Month Backtest", key="btn_backtest"):
         with st.spinner("⏳ Simulating trades... This uses complex AI models and takes ~2-3 minutes. Please be patient."):
            try:
                bt_res = requests.get(f"{API_URL}/backtest/{ticker_input}")
                if bt_res.status_code == 200:
                    bt_data = bt_res.json()
                    if bt_data.get("status") == "success":
                        b1, b2, b3 = st.columns(3)
                        b1.metric("Win Rate", f"{bt_data.get('win_rate')}%")
                        b2.metric("Total Trades", bt_data.get('total_trades'))
                        
                        # Calculate Return from raw data if helpful, or just show trades
                        raw_trades = bt_data.get("data", [])
                        if raw_trades:
                            df_bt = pd.DataFrame(raw_trades)
                            # Simple equity curve approximation
                            st.line_chart(df_bt.set_index('date')[['pred_return', 'actual_return']])
                            st.dataframe(df_bt)
                        else:
                            st.warning("No trades generated in this period (Strategy Conservative).")
                    else:
                        st.error(f"Backtest Failed: {bt_data.get('reason', 'Unknown')}")
                else:
                    st.error(f"API Error: {bt_res.text}")
            except Exception as e:
                st.error(f"Error running backtest: {e}")

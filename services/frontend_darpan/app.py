import streamlit as st
import requests
import pandas as pd
import json
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
    /* WAITING STATE STYLE */
    .waiting { color: #29B6F6; animation: blinker 1.5s linear infinite; }
    @keyframes blinker { 50% { opacity: 0.5; } }
    
    .metric-row { display: flex; justify-content: space-between; margin-top: 10px; }
    .metric-label { font-size: 13px; color: #aaa; }
    .metric-val { font-size: 16px; font-weight: bold; color: #fff; }
    .reasoning-box { background-color: #262730; padding: 15px; border-left: 5px solid #4CAF50; margin-top: 20px; border-radius: 5px; }
    
    /* Top Picks Cards */
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

def display_horizon_card(title, data):
    # Robust empty check for dicts/lists vs pandas objects
    if data is None: return
    if isinstance(data, (dict, list)) and not data: return
    
    verdict = data.get('verdict', 'N/A')
    
    # CSS Selection
    color_class = "hold"
    if verdict in ["BUY", "STRONG BUY"]: color_class = "buy"
    elif verdict == "SELL": color_class = "sell"
    elif verdict == "WAITING": color_class = "waiting"
    
    target = data.get('target')
    sl = data.get('sl')
    
    st.markdown(f"""
    <div class="card">
        <div class="card-title">{title}</div>
        <div class="verdict-text {color_class}">{verdict}</div>
        <div class="metric-row">
            <div>
                <div class="metric-label">Target</div>
                <div class="metric-val">₹{safe_format(target)}</div>
            </div>
            <div style="text-align: right;">
                <div class="metric-label">Stop Loss</div>
                <div class="metric-val">₹{safe_format(sl)}</div>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def display_top_pick(rank, data, label="Top Pick"):
    # Fix for ambiguous truth value error with pandas Series
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

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["🚀 Deep Analysis", "🔎 Stock Finder", "💼 Portfolio"])

# --- TAB 1: DEEP ANALYSIS ---
with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        ticker_input = st.text_input("Enter Ticker (e.g. RELIANCE.NS)", value="RELIANCE.NS")
    with col2:
        st.write("")
        st.write("")
        analyze_btn = st.button("Analyze Stock", use_container_width=True, type="primary")

    if analyze_btn:
        with st.spinner(f"Analyzing {ticker_input}..."):
            try:
                res = requests.get(f"{API_URL}/analysis/{ticker_input}")
                if res.status_code == 200:
                    data = res.json()
                    st.subheader(f"{data.get('company_name', ticker_input)}")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Current Price", f"₹{safe_format(data.get('current_price'))}")
                    m2.metric("Sector", data.get('sector', 'N/A'))
                    source = data.get('source', 'Unknown')
                    
                    if source == 'database': 
                        m3.success("Source: Deep Analysis (Ready)")
                    else: 
                        m3.warning("Source: Live Fetch (Processing...)")
                        st.info("ℹ️ **New Stock Detected:** Full analysis has started in the background. Please wait 30-60 seconds and click 'Analyze Stock' again for the final verdict.")
                        
                    st.divider()
                    c1, c2, c3 = st.columns(3)
                    with c1: display_horizon_card("Short Term (2 Weeks)", data.get('st', {}))
                    with c2: display_horizon_card("Mid Term (2 Months)", data.get('mt', {}))
                    with c3: display_horizon_card("Long Term (1 Year)", data.get('lt', {}))
                    st.markdown(f"""
                    <div class="reasoning-box">
                        <strong>🤖 AI Reasoning:</strong><br>
                        {data.get('reasoning', 'No reasoning available.')}
                    </div>
                    """, unsafe_allow_html=True)
                else: st.error(f"Error: {res.text}")
            except Exception as e: st.error(f"Connection Error: {e}")

# --- TAB 2: STOCK FINDER (UPDATED) ---
with tab2:
    st.header("AI Stock Screener")
    
    horizon_map = {
        "Short Term (14 Days)": "short",
        "Mid Term (60 Days)": "mid",
        "Long Term (1 Year)": "long"
    }
    
    selected_horizon_label = st.radio("Select Investment Horizon", list(horizon_map.keys()), horizontal=True)
    selected_horizon = horizon_map[selected_horizon_label]

    if st.button("Find Top Picks", type="primary"):
        with st.spinner(f"Scanning for best {selected_horizon_label} opportunities..."):
            try:
                res = requests.get(f"{API_URL}/screener/{selected_horizon}")
                
                if res.status_code == 200:
                    opportunities = res.json()
                    if opportunities:
                        df = pd.DataFrame(opportunities)
                        
                        # --- NEW: Extract Sector Status Logic for Display ---
                        # We try to infer if sector caused a downgrade from the reasoning text
                        def get_sector_note(row):
                            reasoning = str(row.get('reasoning', ''))
                            if "Sector Warning" in reasoning:
                                return "⚠️ Bearish Sector"
                            return "✅ OK"
                        
                        df['Sector Status'] = df.apply(get_sector_note, axis=1)

                        # Sort primarily by Confidence, secondary by Upside
                        df = df.sort_values(by=['confidence', 'upside_pct'], ascending=[False, False])
                        
                        # --- TOP 3 DISPLAY ---
                        st.subheader(f"🏆 Top 3 Picks for {selected_horizon_label}")
                        top_cols = st.columns(3)
                        
                        for i in range(min(3, len(df))):
                            row = df.iloc[i]
                            with top_cols[i]:
                                display_top_pick(i+1, row)
                        
                        # --- FULL TABLE ---
                        st.divider()
                        st.subheader("📋 All Opportunities")
                        
                        df['confidence'] = df['confidence'] * 100
                        
                        # Renaming and selecting columns for clean display
                        # ADDED 'reasoning' back to the display columns
                        df_display = df[[
                            'ticker', 'company_name', 'current_price', 
                            'verdict', 'Sector Status', 'upside_pct', 'target_price', 
                            'stop_loss', 'duration_days', 'confidence', 'reasoning'
                        ]]
                        
                        df_display.columns = [
                            "Ticker", "Company", "Price (₹)", 
                            "Verdict", "Sector", "Upside %", "Target (₹)", 
                            "Stop Loss (₹)", "Days", "Conf.", "Reasoning"
                        ]
                        
                        st.dataframe(
                            df_display.style.format({
                                "Price (₹)": "{:.2f}", "Target (₹)": "{:.2f}", 
                                "Stop Loss (₹)": "{:.2f}", "Upside %": "{:.2f}%", 
                                "Conf.": "{:.1f}%", "Days": "{:.0f}"
                            }).applymap(
                                lambda x: "color: orange; font-weight: bold;" if "Bearish" in str(x) else "", 
                                subset=['Sector']
                            ),
                            use_container_width=True,
                            height=400
                        )
                    else:
                        st.info(f"No strong BUY signals found for {selected_horizon_label} today.")
                else:
                    st.error(f"API Error: {res.status_code}")
            except Exception as e:
                st.error(f"API Error: {e}")

# --- TAB 3: PORTFOLIO ---
with tab3:
    st.header("My Portfolio Intelligence")
    
    col_a, col_b = st.columns([1, 4])
    refresh = col_a.button("Refresh Portfolio")
    optimize = col_b.button("🤖 AI Optimize (Max Sharpe Ratio)", type="primary")

    if not os.path.exists('portfolio.json'): st.warning("portfolio.json not found.")
    else:
        with open('portfolio.json', 'r') as f: holdings = json.load(f)

        if refresh:
            try:
                portfolio_list = []
                total_invested = 0
                total_value = 0
                
                with st.spinner("Analyzing..."):
                    for item in holdings:
                        try:
                            res = requests.get(f"{API_URL}/analysis/{item['ticker']}")
                            if res.status_code == 200:
                                data = res.json()
                                cur_price = data.get('current_price', 0) or 0
                                
                                mt_data = data.get('mt', {})
                                target = mt_data.get('target', 0) if mt_data else 0
                                verdict = mt_data.get('verdict', 'N/A') if mt_data else 'N/A'
                                sl = mt_data.get('sl', 0) if mt_data else 0
                                
                                val = cur_price * item['quantity']
                                inv = item['buy_price'] * item['quantity']
                                pl = val - inv 
                                
                                total_invested += inv
                                total_value += val
                                
                                portfolio_list.append({
                                    "Ticker": item['ticker'],
                                    "Qty": item['quantity'],
                                    "Buy Price": item['buy_price'],
                                    "Cur. Price": cur_price,
                                    "P/L": round(val - inv, 2),
                                    "Action (Mid-Term)": verdict,
                                    "Target": target,
                                    "Stop Loss": sl
                                })
                        except: pass
                
                c1, c2, c3 = st.columns(3)
                pl = total_value - total_invested
                c1.metric("Total Invested", f"₹{total_invested:,.0f}")
                c2.metric("Current Value", f"₹{total_value:,.0f}")
                c3.metric("Total P/L", f"₹{pl:,.0f}", delta=f"{(pl/total_invested)*100:.1f}%" if total_invested else "0%")
                
                if portfolio_list:
                    st.dataframe(pd.DataFrame(portfolio_list).style.format({
                        "Buy Price": "{:.2f}", "Cur. Price": "{:.2f}", "P/L": "{:.2f}", 
                        "Target": "{:.2f}", "Stop Loss": "{:.2f}"
                    }), use_container_width=True)
            except Exception as e: st.error(f"Error: {e}")
            
        if optimize:
            with st.spinner("Running Quant Optimization Models..."):
                try:
                    res = requests.post(f"{API_URL}/portfolio/optimize", json=holdings)
                    if res.status_code == 200:
                        opt_data = res.json()
                        st.subheader("🤖 AI Suggested Rebalancing")
                        
                        perf = opt_data.get('performance', [])
                        if perf:
                             st.info(f"Expected Annual Return: {perf[0]*100:.1f}% | Volatility: {perf[1]*100:.1f}% | Sharpe Ratio: {perf[2]:.2f}")
                        
                        suggestions = opt_data.get('suggestions', [])
                        if suggestions:
                            df_opt = pd.DataFrame(suggestions)
                            st.dataframe(
                                df_opt[['ticker', 'current_qty', 'suggested_qty', 'action', 'weight']].style.format({
                                    "weight": "{:.1f}%"
                                }),
                                use_container_width=True
                            )
                        else:
                            st.warning("Optimization failed or no changes needed.")
                    else:
                        st.error(f"Optimization Error: {res.text}")
                except Exception as e:
                    st.error(f"Connection Error: {e}")
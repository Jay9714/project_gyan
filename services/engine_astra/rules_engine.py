from technical_analysis import get_support_resistance_levels

def calculate_stop_loss(current_price, atr, term='short', direction='LONG'):
    multiplier = 1.5 if term == 'short' else 2.5 if term == 'mid' else 3.5
    if direction == 'LONG':
        sl = current_price - (atr * multiplier)
    else:
        sl = current_price + (atr * multiplier)
    return round(sl, 2)


def determine_risk_level(altman_z, piotroski_f, beneish_m, vol_pct):
    """
    Classify Risk based on Fundamental Health & Volatility.
    """
    risk_score = 0
    
    # Financial Distress (Altman Z)
    if altman_z < 1.8: risk_score += 3 # High Risk
    elif altman_z < 3.0: risk_score += 1 # Grey Zone
    
    # Financial Strength (Piotroski F)
    if piotroski_f < 4: risk_score += 2
    
    # Earnings Manipulation (Beneish M)
    if beneish_m > -1.78: risk_score += 2
    
    # Volatility Risk
    if vol_pct > 0.04: risk_score += 2 # >4% daily move is wildly volatile
    elif vol_pct > 0.02: risk_score += 1
    
    if risk_score >= 5: return "HIGH"
    elif risk_score >= 2: return "MEDIUM"
    return "LOW"

def analyze_timeframe(df, term, current_price, atr, base_verdict, fundamentals, sector_status):
    """
    Analyze specific timeframe (Short, Mid, Long) to determine trend, targets, and local verdict.
    """
    latest = df.iloc[-1]
    reasoning = []
    
    # default
    verdict = base_verdict
    trend = "SIDEWAYS"
    direction = "LONG"
    
    # 1. Trend Detection
    if term == 'short':
        # Short Term: Price vs EMA20, RSI, Momentum
        ema20 = latest['ema_20']
        if current_price > ema20:
            trend = "UP"
            reasoning.append("Price > EMA20 (Bullish).")
        else:
            trend = "DOWN"
            reasoning.append("Price < EMA20 (Bearish).")
            
        rsi = latest['rsi']
        if rsi < 30: reasoning.append("RSI Oversold.")
        elif rsi > 70: reasoning.append("RSI Overbought.")
            
    elif term == 'mid':
        # Mid Term: Price vs EMA50, MACD
        ema50 = latest['ema_50']
        if current_price > ema50:
            trend = "UP"
            reasoning.append("Price > EMA50 (Bullish).")
        else:
            trend = "DOWN"
            reasoning.append("Price < EMA50 (Bearish).")
            
        if latest['macd'] > latest['macd_signal']: reasoning.append("MACD Bullish Cross.")
        else: reasoning.append("MACD Bearish.")
        
    elif term == 'long':
        # Long Term: Price vs EMA200, Fundamentals
        ema200 = latest['ema_200']
        if current_price > ema200:
            trend = "UP"
            reasoning.append("Price > EMA200 (Long-Term Bull).")
        else:
            trend = "DOWN"
            reasoning.append("Price < EMA200 (Long-Term Bear).")
            
    # 2. Refine Verdict based on Trend
    if trend == "DOWN" and base_verdict in ["BUY", "STRONG BUY"]:
        verdict = "ACCUMULATE" # Wait for reversal
        if term == 'long': verdict = "HOLD" # If LT is down, be careful
        
    if trend == "UP" and base_verdict == "SELL":
        verdict = "HOLD" # Don't sell in uptrend
        
    # 3. Targets
    # Assume Long strategy for Targets usually, unless explicit Short logic needed.
    # We set targets above current price for Bullish/Accumulate/Hold.
    # If Bearish/Sell, maybe lower?
    # Simple logic: Targets are upside potential.
    
    # Calculate Stop Loss
    if verdict == "SELL":
        direction = "SHORT"
    else:
        direction = "LONG"
        
    stop_loss = calculate_stop_loss(current_price, atr, term, direction)
    
    risk = abs(current_price - stop_loss)
    if risk == 0: risk = current_price * 0.05 # Fallback
    
    if direction == "LONG":
        target_conservative = current_price + (risk * 2.0)
        target_aggressive = current_price + (risk * 3.5)
    else:
        target_conservative = current_price - (risk * 2.0)
        target_aggressive = current_price - (risk * 3.5)
        
    rr = round(abs(target_conservative - current_price) / risk, 2)
    
    return {
        "verdict": verdict,
        "trend": trend,
        "target_conservative": round(target_conservative, 2),
        "target_aggressive": round(target_aggressive, 2),
        "stop_loss": round(stop_loss, 2),
        "risk_reward": rr,
        "reasoning": reasoning
    }

# ... (Start of analyze_stock)
def analyze_stock(ticker, df, fundamentals, sentiment_score, ai_confidence, forecast_df, sector="Unknown", sector_status="NEUTRAL", catalyst_score=0.0):
    """
    Master Analysis Function.
    df: DataFrame containing TA features.
    """
    latest = df.iloc[-1]
    current_price = latest['close'] # Lowercase 'close'
    atr = latest.get('atr', current_price * 0.02)
    rsi = latest['rsi']
    macd = latest['macd']
    
    # S&R Detection
    # Note: get_support_resistance_levels might expect 'High'/'Low'. 
    # Check if df has 'high'/'low' (lowercase) or 'High'/'Low'. 
    # Since ai_df renamed them to lowercase in tasks.py line 249, we pass the lowercase ones.
    # But get_support_resistance_levels in technical_analysis.py likely uses 'High'/'Low'.
    # We should normalize column names or handle it.
    
    # Let's fix column access here first.
    sr_levels = get_support_resistance_levels(df) #df is ai_df (lowercase cols)
    nearest_support = max([l[0] for l in sr_levels if l[1] == 'Support' and l[0] < current_price], default=0)
    nearest_resistance = min([l[0] for l in sr_levels if l[1] == 'Resistance' and l[0] > current_price], default=current_price*1.5)
    
    dist_support = (current_price - nearest_support) / current_price
    dist_resistance = (nearest_resistance - current_price) / current_price
    
    near_support = dist_support < 0.03 # Within 3%
    near_resistance = dist_resistance < 0.03 

    # --- 1. BASE SCORING ---
    score = 0
    if rsi < 30: score += 15 
    elif 40 <= rsi <= 70: score += 10 
    
    if latest['close'] > latest['ema_50']: score += 20
    if latest['macd'] > latest['macd_signal']: score += 15
    if latest['vol_spike']: score += 5
    
    # S&R Scoring
    if near_support: score += 10
    if near_resistance: score -= 10 # Breakout or Reject? Assume Reject risk first.
    
    if fundamentals.get('piotroski_f_score', 0) >= 6: score += 10
    if fundamentals.get('revenue_growth', 0) > 0.10: score += 10
    
    if sentiment_score > 0.1: score += 10
    
    # Catalyst Boost
    score += (catalyst_score * 20)
    
    # Base Verdict
    base_verdict = "HOLD"
    if score >= 75: base_verdict = "STRONG BUY"
    elif score >= 50: base_verdict = "BUY"
    elif score >= 30: base_verdict = "ACCUMULATE"
    elif score < 20: base_verdict = "SELL"
    
    # Sector Check
    if sector_status == "BEARISH" and base_verdict in ["BUY", "STRONG BUY"]:
        base_verdict = "ACCUMULATE" # Downgrade
        
    # --- 2. TIMEFRAME ANALYSIS ---
    st_res = analyze_timeframe(df, 'short', current_price, atr, base_verdict, fundamentals, sector_status)
    mt_res = analyze_timeframe(df, 'mid', current_price, atr, base_verdict, fundamentals, sector_status)
    lt_res = analyze_timeframe(df, 'long', current_price, atr, base_verdict, fundamentals, sector_status)
    
    # --- 3. RISK ASSESSMENT ---
    vol_pct = atr / current_price
    risk_badge = determine_risk_level(
        fundamentals.get('altman_z_score', 3), 
        fundamentals.get('piotroski_f_score', 5), 
        fundamentals.get('beneish_m_score', -3), 
        vol_pct
    )
    
    # --- 4. CONSTRUCT OUTPUT ---
    # Merge reasoning
    final_reasoning = (
        f"**Technical Score:** {score}/100\n"
        f"**Risk Level:** {risk_badge}\n"
        f"**Strategy:** {st_res['trend']} (ST) -> {mt_res['trend']} (MT)\n\n"
        f"**Short Term:** {st_res['verdict']} - {' '.join(st_res['reasoning'])}\n"
        f"**Mid Term:** {mt_res['verdict']} - {' '.join(mt_res['reasoning'])}\n"
        f"**Long Term:** {lt_res['verdict']} - {' '.join(lt_res['reasoning'])}\n"
    )

    return {
        "st": {
            "verdict": st_res['verdict'], 
            "target": st_res['target_conservative'], 
            "target_agg": st_res['target_aggressive'],
            "sl": st_res['stop_loss'],
            "rr": st_res['risk_reward']
        },
        "mt": {
            "verdict": mt_res['verdict'], 
            "target": mt_res['target_conservative'], 
            "target_agg": mt_res['target_aggressive'],
            "sl": mt_res['stop_loss'],
            "rr": mt_res['risk_reward']
        },
        "lt": {
            "verdict": lt_res['verdict'], 
            "target": lt_res['target_conservative'], 
            "target_agg": lt_res['target_aggressive'],
            "sl": lt_res['stop_loss'],
            "rr": lt_res['risk_reward']
        },
        "risk_level": risk_badge,
        "reasoning": final_reasoning,
        "ai_confidence": ai_confidence
    }


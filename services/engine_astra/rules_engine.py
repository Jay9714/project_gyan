def calculate_stop_loss(current_price, atr, term='short'):
    multiplier = 1.5 if term == 'short' else 2.0 if term == 'mid' else 3.0
    sl = current_price - (atr * multiplier)
    return round(sl, 2)

def calculate_momentum_target(current_price, atr, term='short'):
    multiplier = 3.0 if term == 'short' else 8.0 if term == 'mid' else 15.0
    target = current_price + (atr * multiplier)
    return round(target, 2)

def analyze_stock(ticker, current_price, rsi, macd, ema_50, atr, ai_confidence, prophet_forecast, fundamentals, sentiment_score):
    reasoning = []
    
    # Data
    def get_pred(days):
        try: return prophet_forecast.iloc[days]['yhat']
        except: return current_price
        
    st_target = get_pred(14)
    mt_target = get_pred(60) 
    lt_target = get_pred(365)
    
    # Risk Scores
    f_score = fundamentals.get('piotroski_f_score', 5)
    z_score = fundamentals.get('altman_z_score', 3.0)
    m_score = fundamentals.get('beneish_m_score', -2.5)

    # --- TURNAROUND LOGIC (With Safety) ---
    is_uptrend = current_price > ema_50
    is_positive_news = sentiment_score > 0.1
    is_ai_bearish = st_target < current_price
    
    # SAFETY: Only allow turnaround if NOT in bankruptcy zone
    is_safe = z_score > 1.8 
    
    using_momentum_target = False
    if is_uptrend and is_positive_news and is_ai_bearish and is_safe:
        using_momentum_target = True
        reasoning.append("🚀 Turnaround Detected (Momentum Override)")
        st_target = calculate_momentum_target(current_price, atr, 'short')
        mt_target = calculate_momentum_target(current_price, atr, 'mid')
        lt_target = calculate_momentum_target(current_price, atr, 'long')
    
    # ... (Scoring Logic) ...
    score = 0
    if rsi < 40: score += 1
    if macd > 0: score += 1
    if is_uptrend: score += 1
    
    # Fundamental Boost & Penalties (Pro Logic)
    if f_score >= 7: score += 2; reasoning.append("💎 High Quality")
    elif f_score <= 4: score -= 1; reasoning.append("⚠️ Low Quality")
    
    if z_score < 1.8: score -= 3; reasoning.append("⛔ Distress Risk")
    
    if m_score > -1.78: score -= 3; reasoning.append("⛔ Accounting Risk")
    
    # News
    if sentiment_score > 0.2: score += 2
    elif sentiment_score < -0.2: score -= 2

    # --- UPDATED VERDICT LOGIC ---
    def get_verdict(term_score, target, price):
        # Calculate potential percentage change
        upside = ((target - price) / price) * 100
        
        # 1. Hard Vetoes (Bankruptcy/Fraud)
        if z_score < 1.8: return "AVOID" 
        if m_score > -1.78: return "AVOID"
        
        # 2. Momentum Override
        if using_momentum_target:
             if term_score >= 2: return "BUY"
             return "ACCUMULATE"

        # 3. SELL Logic (The Fix)
        # If target is lower than price...
        if target < price:
            # If the drop is significant (> 2%), it is a SELL
            if upside < -2.0: return "SELL"
            # If it's a minor drop (0% to -2%), we can HOLD/WATCH
            return "HOLD"
        
        # 4. BUY Logic
        if upside > 15 and term_score >= 4: return "STRONG BUY"
        if upside > 5 and term_score >= 3.5: return "BUY"
        if term_score >= 2: return "ACCUMULATE"
        
        # Default
        return "HOLD"

    # ... (Final Calculation) ...
    st_verdict = get_verdict(score + (0.2 * ai_confidence * 100), st_target, current_price)
    mt_verdict = get_verdict(score + 1.0, mt_target, current_price)
    lt_verdict = get_verdict(score, lt_target, current_price)
    
    st_sl = calculate_stop_loss(current_price, atr, 'short')
    mt_sl = calculate_stop_loss(current_price, atr, 'mid')
    lt_sl = calculate_stop_loss(current_price, atr, 'long')

    return {
        "st": {"verdict": st_verdict, "target": round(st_target, 2), "sl": st_sl},
        "mt": {"verdict": mt_verdict, "target": round(mt_target, 2), "sl": mt_sl},
        "lt": {"verdict": lt_verdict, "target": round(lt_target, 2), "sl": lt_sl},
        "reasoning": " | ".join(reasoning),
        "ai_confidence": ai_confidence
    }
def calculate_stop_loss(current_price, atr, term='short'):
    multiplier = 1.5 if term == 'short' else 2.0 if term == 'mid' else 3.0
    sl = current_price - (atr * multiplier)
    return round(sl, 2)

def calculate_momentum_target(current_price, atr, term='short'):
    multiplier = 3.0 if term == 'short' else 8.0 if term == 'mid' else 15.0
    target = current_price + (atr * multiplier)
    return round(target, 2)

def analyze_stock(ticker, current_price, rsi, macd, ema_50, atr, ai_confidence, prophet_forecast, fundamentals, sentiment_score, sector="Unknown"):
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

    # --- SECTOR ADAPTIVE LOGIC (ROBUST) ---
    # These sectors naturally carry high debt or have different working capital structures.
    # We should NOT penalize them with the standard Altman Z-Score model.
    capital_intensive_keywords = [
        'real estate', 'financial', 'banking', 'utilities', 
        'infrastructure', 'power', 'telecom', 'capital goods', 
        'construction', 'insurance', 'nbfc', 'industrials'
    ]
    
    # Check if the sector matches ANY of these keywords (Case Insensitive)
    is_capital_intensive = any(keyword in str(sector).lower() for keyword in capital_intensive_keywords)
    
    ignore_z_score = False
    if is_capital_intensive:
        ignore_z_score = True
        reasoning.append(f"ℹ️ {sector} Sector (Risk Rules Relaxed)")

    # --- TURNAROUND LOGIC ---
    is_uptrend = current_price > ema_50
    is_positive_news = sentiment_score > 0.1
    is_ai_bearish = st_target < current_price
    
    # SAFETY: Only allow turnaround if NOT in bankruptcy zone (unless ignored)
    is_safe = z_score > 1.8 or ignore_z_score
    
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
    
    # Fundamental Boost & Penalties (Adaptive)
    if f_score >= 7: score += 2; reasoning.append("💎 High Quality")
    elif f_score <= 3: score -= 1; reasoning.append("⚠️ Low Quality")
    
    # Only apply Z-Score penalty if NOT a capital intensive sector
    if not ignore_z_score:
        if z_score < 1.8: score -= 3; reasoning.append("⛔ Distress Risk")
    
    if m_score > -1.78: score -= 3; reasoning.append("⛔ Accounting Risk")
    
    if sentiment_score > 0.2: score += 2
    elif sentiment_score < -0.2: score -= 2

    # --- UPDATED VERDICT LOGIC ---
    def get_verdict(term_score, target, price):
        upside = ((target - price) / price) * 100
        
        # 1. Hard Vetoes
        if not ignore_z_score and z_score < 1.8: return "AVOID" 
        if m_score > -1.78: return "AVOID"
        
        # 2. Momentum Override
        if using_momentum_target:
             if term_score >= 2: return "BUY"
             return "ACCUMULATE"

        # 3. SELL LOGIC
        if target < price:
            if upside < -2.0: return "SELL"
            return "HOLD"
        
        # 4. BUY LOGIC
        if upside > 15 and term_score >= 4: return "STRONG BUY"
        if upside > 5 and term_score >= 3.5: return "BUY"
        if term_score >= 2: return "ACCUMULATE"
        return "HOLD"

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
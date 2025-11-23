def calculate_stop_loss(current_price, atr, term='short'):
    multiplier = 1.5 if term == 'short' else 2.0 if term == 'mid' else 3.0
    sl = current_price - (atr * multiplier)
    return round(sl, 2)

def analyze_stock(ticker, current_price, rsi, macd, ema_50, atr, ai_confidence, prophet_forecast, fundamentals):
    """
    Updated Decision Layer with SAFETY CHECKS.
    """
    reasoning = []
    
    # Extract Fundamentals
    roe = fundamentals.get('roe') or 0
    de_ratio = fundamentals.get('debt_to_equity') or 0
    growth = fundamentals.get('revenue_growth') or 0
    
    # --- 1. Extract Predictions ---
    def get_pred(days):
        try: return prophet_forecast.iloc[days]['yhat']
        except: return current_price

    st_target = get_pred(14)
    mt_target = get_pred(60)
    lt_target = get_pred(365)

    # --- 2. Scoring Logic ---
    
    # TECHNICAL SCORE (0-5)
    tech_score = 0
    if rsi < 40: 
        tech_score += 1
        reasoning.append("✅ RSI Oversold")
    if macd > 0: tech_score += 1
    if current_price > ema_50: 
        tech_score += 1
        reasoning.append("✅ Uptrend")
    
    # FUNDAMENTAL SCORE (0-5)
    funda_score = 0
    if roe > 0.15: 
        funda_score += 2
        reasoning.append("✅ Strong ROE")
    if de_ratio < 0.5: funda_score += 1
    elif de_ratio > 2.0: 
        funda_score -= 2
        reasoning.append("⚠️ High Debt")
    if growth > 0.10: 
        funda_score += 2
        reasoning.append("🚀 High Growth")

    # --- 3. Verdict Generation with SAFETY CHECKS ---
    
    def get_verdict(score, target, price):
        upside = ((target - price) / price) * 100
        
        # SAFETY RULE 1: If AI predicts a crash (>2% drop), NEVER Buy.
        if upside < -2.0:
            return "SELL"
        
        # SAFETY RULE 2: If upside is tiny (<2%), just Hold.
        if upside < 2.0:
            return "HOLD"

        # Only if AI agrees (Upside > 2%), check the Score
        if score >= 3.5: return "BUY"
        if score >= 2.0: return "ACCUMULATE"
        return "HOLD"

    # Calculate Scores for each horizon
    # Short Term: 80% Tech, 20% Funda
    st_score_total = tech_score + (0.2 * funda_score)
    st_verdict = get_verdict(st_score_total, st_target, current_price)

    # Mid Term: 50% Tech, 50% Funda
    mt_score_total = tech_score + funda_score
    mt_verdict = get_verdict(mt_score_total, mt_target, current_price)
    
    # Long Term: 20% Tech, 80% Funda
    lt_score_total = (0.2 * tech_score) + funda_score
    lt_verdict = get_verdict(lt_score_total, lt_target, current_price)
        
    # Stop Losses
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
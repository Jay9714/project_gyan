def calculate_stop_loss(current_price, atr, term='short'):
    multiplier = 1.5 if term == 'short' else 2.0 if term == 'mid' else 3.0
    sl = current_price - (atr * multiplier)
    return round(sl, 2)

def analyze_stock(ticker, current_price, rsi, macd, ema_50, atr, ai_confidence, prophet_forecast, fundamentals):
    """
    Updated Decision Layer: Now considers Fundamentals (ROE, Debt, Growth).
    """
    reasoning = []
    
    # Extract new metrics (default to 0/safe values if None)
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
    if rsi < 40: tech_score += 1
    if macd > 0: tech_score += 1
    if current_price > ema_50: tech_score += 1
    
    # FUNDAMENTAL SCORE (0-5) - NEW!
    funda_score = 0
    if roe > 0.15: # 15% ROE is good
        funda_score += 2
        reasoning.append("✅ Strong ROE (>15%)")
    if de_ratio < 0.5: # Low debt
        funda_score += 1
        reasoning.append("✅ Low Debt")
    elif de_ratio > 2.0: # High debt
        funda_score -= 2
        reasoning.append("⚠️ High Debt")
    if growth > 0.10: # 10% Growth
        funda_score += 2
        reasoning.append("🚀 High Growth")

    # --- 3. Verdicts ---
    
    # SHORT TERM: 80% Technical, 20% Fundamental
    st_total = tech_score + (0.2 * funda_score)
    st_verdict = "BUY" if st_total >= 2.5 else "SELL" if st_total < 1 else "HOLD"

    # MID TERM: 50% Technical, 50% Fundamental
    mt_total = tech_score + funda_score
    mt_verdict = "BUY" if mt_total >= 4 else "SELL" if mt_total < 2 else "HOLD"
    
    # LONG TERM: 20% Technical, 80% Fundamental + AI Projection
    lt_upside = ((lt_target - current_price) / current_price) * 100
    lt_verdict = "BUY" if (funda_score >= 3 and lt_upside > 15) else "HOLD"

    # --- 4. Safety Checks ---
    if current_price < 0.9 * lt_target: # If price is way below target
        lt_verdict = "ACCUMULATE"
        
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
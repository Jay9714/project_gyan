def calculate_stop_loss(current_price, atr, term='short'):
    multiplier = 1.5 if term == 'short' else 2.0 if term == 'mid' else 3.0
    sl = current_price - (atr * multiplier)
    return round(sl, 2)

def analyze_stock(ticker, current_price, rsi, macd, ema_50, atr, ai_confidence, prophet_forecast, fundamentals):
    reasoning = []
    
    # Extract Fundamentals & Risk Scores
    roe = fundamentals.get('roe') or 0
    de_ratio = fundamentals.get('debt_to_equity') or 0
    growth = fundamentals.get('revenue_growth') or 0
    f_score = fundamentals.get('piotroski_f_score', 5)
    z_score = fundamentals.get('altman_z_score', 3.0)
    
    # Predictions
    def get_pred(days):
        try: return prophet_forecast.iloc[days]['yhat']
        except: return current_price
    st_target = get_pred(14); mt_target = get_pred(60); lt_target = get_pred(365)

    # --- SCORING ---
    tech_score = 0
    if rsi < 40: tech_score += 1; reasoning.append("✅ RSI Oversold")
    if macd > 0: tech_score += 1
    if current_price > ema_50: tech_score += 1; reasoning.append("✅ Uptrend")

    funda_score = 0
    if roe > 0.15: funda_score += 2; reasoning.append("✅ Strong ROE")
    if de_ratio < 0.5: funda_score += 1
    elif de_ratio > 2.0: funda_score -= 2; reasoning.append("⚠️ High Debt")
    
    # New Risk Scoring
    if f_score >= 7: 
        funda_score += 2
        reasoning.append(f"💎 High Quality (F-Score {f_score})")
    elif f_score <= 3:
        funda_score -= 2
        reasoning.append(f"⚠️ Low Quality (F-Score {f_score})")
        
    if z_score < 1.8:
        funda_score -= 3 # Huge penalty for bankruptcy risk
        reasoning.append(f"⛔ Distress Risk (Z-Score {z_score})")

    # Verdict Helper
    def get_verdict(score, target, price):
        upside = ((target - price) / price) * 100
        if upside < -2.0: return "SELL"
        if upside < 2.0: return "HOLD"
        if score >= 4.0: return "BUY" # Higher threshold for BUY
        if score >= 2.0: return "ACCUMULATE"
        return "HOLD"

    # Weighted Scores
    st_verdict = get_verdict(tech_score + (0.2 * funda_score), st_target, current_price)
    mt_verdict = get_verdict(tech_score + funda_score, mt_target, current_price)
    # Long Term heavily weights the new F-Score and Z-Score via funda_score
    lt_verdict = get_verdict((0.2 * tech_score) + funda_score, lt_target, current_price)

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
def calculate_stop_loss(current_price, atr, term='short'):
    multiplier = 1.5 if term == 'short' else 2.0 if term == 'mid' else 3.0
    sl = current_price - (atr * multiplier)
    return round(sl, 2)

def calculate_momentum_target(current_price, atr, term='short'):
    """
    Calculates a target based on Volatility (ATR) and Momentum.
    Used when AI is too bearish on a turnaround stock.
    """
    # Projecting 2x ATR moves as targets
    multiplier = 2.0 if term == 'short' else 5.0 if term == 'mid' else 10.0
    target = current_price + (atr * multiplier)
    return round(target, 2)

def analyze_stock(ticker, current_price, rsi, macd, ema_50, atr, ai_confidence, prophet_forecast, fundamentals, sentiment_score):
    reasoning = []
    
    # Fundamentals
    roe = fundamentals.get('roe') or 0
    de_ratio = fundamentals.get('debt_to_equity') or 0
    growth = fundamentals.get('revenue_growth') or 0
    
    # Predictions (Prophet)
    def get_pred(days):
        try: return prophet_forecast.iloc[days]['yhat']
        except: return current_price
    st_target = get_pred(14); mt_target = get_pred(60); lt_target = get_pred(365)

    # --- 1. IDENTIFY MARKET CONDITIONS ---
    is_uptrend = current_price > ema_50
    is_positive_news = sentiment_score > 0.1
    is_ai_bearish = st_target < current_price
    
    # --- 2. TURNAROUND LOGIC (THE FIX) ---
    # If Trend is UP + News is GOOD + AI is WRONG (Bearish) -> Override AI
    using_momentum_target = False
    
    if is_uptrend and is_positive_news and is_ai_bearish:
        using_momentum_target = True
        reasoning.append("🚀 Turnaround Detected (Momentum Override)")
        st_target = calculate_momentum_target(current_price, atr, 'short')
        mt_target = calculate_momentum_target(current_price, atr, 'mid')
        lt_target = calculate_momentum_target(current_price, atr, 'long')

    # --- 3. SCORING ---
    score = 0
    
    # Tech
    if rsi < 40: score += 1; reasoning.append("✅ RSI Oversold")
    elif rsi > 75: score -= 1; reasoning.append("⚠️ RSI Overbought")
    if is_uptrend: score += 1; reasoning.append("✅ Uptrend")
    if macd > 0: score += 1
    
    # Funda
    if roe > 0.15: score += 2; reasoning.append("✅ Strong ROE")
    if growth > 0.10: score += 2; reasoning.append("🚀 High Growth")
    
    # News
    if sentiment_score > 0.2: score += 2; reasoning.append(f"📰 Positive News ({sentiment_score})")
    elif sentiment_score < -0.2: score -= 2; reasoning.append("⚠️ Negative News")

    # --- 4. VERDICT ---
    def get_verdict(term_score, target, price):
        upside = ((target - price) / price) * 100
        
        if using_momentum_target:
             # If we forced a momentum target, trust the trend/news score
             if term_score >= 2: return "BUY"
             return "ACCUMULATE"

        if target < price: return "HOLD" # Don't sell uptrends just because target is low
        
        if upside > 5 and term_score >= 3.5: return "BUY"
        if term_score >= 2: return "ACCUMULATE"
        return "HOLD"

    st_verdict = get_verdict(score, st_target, current_price)
    mt_verdict = get_verdict(score, mt_target, current_price)
    lt_verdict = get_verdict(score, lt_target, current_price)

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
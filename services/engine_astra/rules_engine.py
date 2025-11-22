def analyze_stock(ticker, current_price, rsi, macd, ema_50, ai_confidence, prophet_forecast):
    """
    The 'Hybrid Decision Layer'.
    Combines Technicals + AI to generate a verdict.
    """
    verdict = "HOLD"
    reasoning = []
    
    # --- 1. Technical Analysis Rules ---
    if rsi < 30:
        reasoning.append("RSI Oversold (Bullish)")
    elif rsi > 70:
        reasoning.append("RSI Overbought (Bearish)")
        
    if current_price > ema_50:
        reasoning.append("Price > 50 EMA (Uptrend)")
    else:
        reasoning.append("Price < 50 EMA (Downtrend)")
        
    # --- 2. AI Analysis Rules ---
    # Get the predicted price 30 days from now
    future_price = prophet_forecast.iloc[-1]['yhat']
    upside = ((future_price - current_price) / current_price) * 100
    
    reasoning.append(f"AI predicts {upside:.1f}% move")
    
    # --- 3. Final Decision Logic ---
    score = 0
    
    # Bullish signals
    if rsi < 40: score += 1
    if macd > 0: score += 1
    if current_price > ema_50: score += 1
    if upside > 5: score += 2 # Strong AI prediction weights more
    
    # Bearish signals
    if rsi > 70: score -= 1
    if current_price < ema_50: score -= 1
    if upside < -2: score -= 2
    
    # The Verdict
    # We only trust the AI if confidence is decent (> 50%)
    if score >= 3 and ai_confidence > 0.5:
        verdict = "BUY"
    elif score <= -2:
        verdict = "SELL"
    else:
        verdict = "HOLD"
        
    return {
        "verdict": verdict,
        "target_price": round(future_price, 2),
        "ai_confidence": round(ai_confidence * 100, 1),
        "reasoning": " | ".join(reasoning)
    }
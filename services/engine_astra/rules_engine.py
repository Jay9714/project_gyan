def calculate_stop_loss(current_price, atr, term='short'):
    multiplier = 1.5 if term == 'short' else 2.0 if term == 'mid' else 3.0
    sl = current_price - (atr * multiplier)
    return round(sl, 2)

def calculate_momentum_target(current_price, atr, term='short'):
    multiplier = 3.0 if term == 'short' else 8.0 if term == 'mid' else 15.0
    target = current_price + (atr * multiplier)
    return round(target, 2)

def analyze_stock(ticker, current_price, rsi, macd, ema_50, atr, ai_confidence, prophet_forecast, fundamentals, sentiment_score, sector="Unknown", sector_status="NEUTRAL"):
    
    # --- 1. DATA PREP ---
    def get_pred(days):
        try: return prophet_forecast.iloc[days]['yhat']
        except: return current_price
        
    st_target = get_pred(14)
    mt_target = get_pred(60) 
    lt_target = get_pred(365)
    
    f_score = fundamentals.get('piotroski_f_score', 5)
    z_score = fundamentals.get('altman_z_score', 3.0)
    m_score = fundamentals.get('beneish_m_score', -2.5)

    # --- 2. SECTOR ADAPTIVE LOGIC ---
    capital_intensive_keywords = [
        'real estate', 'financial', 'banking', 'utilities', 
        'infrastructure', 'power', 'telecom', 'capital goods', 
        'construction', 'insurance', 'nbfc', 'industrials'
    ]
    is_capital_intensive = any(keyword in str(sector).lower() for keyword in capital_intensive_keywords)
    ignore_z_score = True if is_capital_intensive else False

    # --- 3. TURNAROUND LOGIC ---
    is_uptrend = current_price > ema_50
    is_positive_news = sentiment_score > 0.1
    is_ai_bearish = st_target < current_price
    is_safe = z_score > 1.8 or ignore_z_score
    
    using_momentum_target = False
    if is_uptrend and is_positive_news and is_ai_bearish and is_safe:
        using_momentum_target = True
        st_target = calculate_momentum_target(current_price, atr, 'short')
        mt_target = calculate_momentum_target(current_price, atr, 'mid')
        lt_target = calculate_momentum_target(current_price, atr, 'long')
    
    # --- 4. SCORING ---
    score = 0
    if rsi < 40: score += 1
    if macd > 0: score += 1
    if is_uptrend: score += 1
    
    if f_score >= 7: score += 2
    elif f_score <= 3: score -= 1
    
    if not ignore_z_score and z_score < 1.8: score -= 3
    if m_score > -1.78: score -= 3
    
    if sentiment_score > 0.2: score += 2
    elif sentiment_score < -0.2: score -= 2

    # --- 5. VERDICT GENERATION ---
    upside = ((st_target - current_price) / current_price) * 100
    
    verdict = "HOLD"
    if not ignore_z_score and z_score < 1.8: verdict = "AVOID"
    elif m_score > -1.78: verdict = "AVOID"
    elif using_momentum_target:
         verdict = "BUY" if score >= 2 else "ACCUMULATE"
    elif st_target < current_price:
        verdict = "SELL" if upside < -2.0 else "HOLD"
    elif upside > 15 and score >= 4: verdict = "STRONG BUY"
    elif upside > 5 and score >= 3.5: verdict = "BUY"
    elif score >= 2: verdict = "ACCUMULATE"

    # --- 6. SECTOR OVERRIDE (PHASE 2 UPGRADE) ---
    sector_downgrade = False
    if verdict in ["BUY", "STRONG BUY"] and sector_status == "BEARISH":
        verdict = "HOLD"
        sector_downgrade = True

    # --- 7. RICH REASONING GENERATION ---
    reasoning_lines = []
    
    # Verdict Explain
    reasoning_lines.append(f"### 🎯 **Final Verdict: {verdict}**")
    if sector_downgrade:
        reasoning_lines.append(f"⚠️ **Sector Warning:** While the stock looks good, the '{sector}' sector is currently **BEARISH**. We have downgraded the rating to **HOLD** to avoid fighting the trend.")
    elif verdict == "STRONG BUY":
        reasoning_lines.append("High conviction. Significant upside potential (>15%) combined with strong fundamentals.")
    elif verdict == "BUY":
        reasoning_lines.append("Solid upside potential (>5%) supported by decent quality scores.")
    elif verdict == "ACCUMULATE":
        reasoning_lines.append("Good stock in a dip. Safe to accumulate slowly.")
    elif verdict == "SELL":
        reasoning_lines.append(f"**⚠️ Downside Alert:** AI predicts a drop of {upside:.1f}%.")
    elif verdict == "AVOID":
        reasoning_lines.append("**⛔ Red Flag:** Distress Risk detected.")
    elif verdict == "HOLD":
        reasoning_lines.append("No clear signal. Wait for breakout.")

    # AI & Math
    ai_msg = f"\n**🤖 AI Model Output:**\n"
    ai_msg += f"- **Target:** ₹{st_target} ({upside:+.1f}%)\n"
    ai_msg += f"- **Confidence:** {ai_confidence*100:.0f}%"
    reasoning_lines.append(ai_msg)

    # Sector
    sec_msg = f"\n**🏢 Sector Pulse:**\n"
    status_icon = "🟢" if sector_status == "BULLISH" else "🔴" if sector_status == "BEARISH" else "⚪"
    sec_msg += f"- **{sector}:** {status_icon} {sector_status}\n"
    if is_capital_intensive:
        sec_msg += f"- **Note:** Risk rules relaxed for this sector."
    reasoning_lines.append(sec_msg)

    final_reasoning = "\n".join(reasoning_lines)

    st_sl = calculate_stop_loss(current_price, atr, 'short')
    mt_sl = calculate_stop_loss(current_price, atr, 'mid')
    lt_sl = calculate_stop_loss(current_price, atr, 'long')

    return {
        "st": {"verdict": verdict, "target": round(st_target, 2), "sl": st_sl},
        "mt": {"verdict": verdict, "target": round(mt_target, 2), "sl": mt_sl},
        "lt": {"verdict": verdict, "target": round(lt_target, 2), "sl": lt_sl},
        "reasoning": final_reasoning,
        "ai_confidence": ai_confidence
    }
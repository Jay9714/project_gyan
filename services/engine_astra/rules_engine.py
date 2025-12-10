def calculate_stop_loss(current_price, atr, term='short'):
    multiplier = 1.5 if term == 'short' else 2.0 if term == 'mid' else 3.0
    sl = current_price - (atr * multiplier)
    return round(sl, 2)

def calculate_momentum_target(current_price, atr, term='short'):
    multiplier = 3.0 if term == 'short' else 8.0 if term == 'mid' else 15.0
    target = current_price + (atr * multiplier)
    return round(target, 2)

def analyze_stock(ticker, current_price, rsi, macd, ema_50, atr, ai_confidence, prophet_forecast, fundamentals, sentiment_score, sector="Unknown"):
    
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

    # --- 6. RICH REASONING GENERATION (Markdown) ---
    reasoning_lines = []
    
    # A. Verdict Explanation
    reasoning_lines.append(f"### 🎯 **Final Verdict: {verdict}**")
    if verdict == "STRONG BUY":
        reasoning_lines.append("The AI has high conviction. Significant upside potential (>15%) combined with strong fundamentals and technical momentum.")
    elif verdict == "BUY":
        reasoning_lines.append("Solid upside potential (>5%) supported by decent quality scores. A good entry point.")
    elif verdict == "ACCUMULATE":
        reasoning_lines.append("Good fundamental stock currently in a dip or consolidation. Safe to accumulate slowly for the long term.")
    elif verdict == "SELL":
        reasoning_lines.append(f"**⚠️ Downside Alert:** The AI predicts a price drop of {upside:.1f}% in the short term. Profit booking advised.")
    elif verdict == "AVOID":
        reasoning_lines.append("**⛔ Red Flag:** Critical financial distress or accounting irregularities detected. Capital preservation is priority.")
    elif verdict == "HOLD":
        reasoning_lines.append("No clear directional signal. Price is predicted to remain flat or signals are conflicting. Wait for a breakout.")

    # B. AI & Math
    ai_msg = f"\n**🤖 AI Model Output:**\n"
    if using_momentum_target:
        ai_msg += f"- **Strategy:** Momentum Override (Trend Following)\n"
    else:
        ai_msg += f"- **Strategy:** Value/Growth Regression\n"
    ai_msg += f"- **Target Price:** ₹{st_target} (vs Current ₹{current_price})\n"
    ai_msg += f"- **Expected Return:** {upside:+.1f}%\n"
    ai_msg += f"- **Confidence:** {ai_confidence*100:.0f}% (Based on historical accuracy)"
    reasoning_lines.append(ai_msg)

    # C. Sector Context
    sec_msg = f"\n**🏢 Sector Analysis:**\n"
    if is_capital_intensive:
        sec_msg += f"- **Sector:** {sector}\n"
        sec_msg += f"- **Context:** Capital Intensive Sector. Standard debt/risk rules (like Altman Z-Score) have been **relaxed** to avoid false alarms."
    else:
        sec_msg += f"- **Sector:** {sector}\n"
        sec_msg += f"- **Context:** Standard industry. Strict financial health checks applied."
    reasoning_lines.append(sec_msg)

    # D. Health Check
    health_msg = f"\n**🩺 Health Check:**\n"
    health_msg += f"- **Technical:** {'Bullish (Uptrend)' if is_uptrend else 'Bearish (Downtrend)'} | RSI: {rsi:.1f}\n"
    health_msg += f"- **Quality (Piotroski):** {f_score}/9 ({'High' if f_score >= 7 else 'Low' if f_score <= 4 else 'Avg'})\n"
    
    if not ignore_z_score:
        health_msg += f"- **Bankruptcy Risk (Z-Score):** {z_score:.2f} ({'Safe' if z_score > 2.0 else 'Risk'})\n"
    else:
        health_msg += f"- **Bankruptcy Risk:** N/A (Sector Exempt)\n"
        
    if m_score > -1.78:
        health_msg += f"- **Accounting:** ⚠️ Possible Manipulation (M-Score: {m_score:.2f})"
    else:
        health_msg += f"- **Accounting:** Clean (M-Score: {m_score:.2f})"
        
    reasoning_lines.append(health_msg)

    final_reasoning = "\n".join(reasoning_lines)

    # --- 7. RETURN ---
    # Calc Targets
    st_sl = calculate_stop_loss(current_price, atr, 'short')
    mt_sl = calculate_stop_loss(current_price, atr, 'mid')
    lt_sl = calculate_stop_loss(current_price, atr, 'long')

    # Assign verdicts to all timeframes based on the main verdict logic 
    # (Simplified for consistency, can be split if needed)
    st_verdict = verdict
    mt_verdict = verdict 
    lt_verdict = verdict 

    return {
        "st": {"verdict": st_verdict, "target": round(st_target, 2), "sl": st_sl},
        "mt": {"verdict": mt_verdict, "target": round(mt_target, 2), "sl": mt_sl},
        "lt": {"verdict": lt_verdict, "target": round(lt_target, 2), "sl": lt_sl},
        "reasoning": final_reasoning,
        "ai_confidence": ai_confidence
    }
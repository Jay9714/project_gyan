import pandas as pd
import numpy as np
import math

# --- Helper Functions ---
def _find_first_row(df, keywords):
    """Return the first index label in df that contains any of the keywords (case-insensitive)."""
    if df.empty: return None
    low_index = [str(i).lower() for i in df.index]
    for kw in keywords:
        kwl = kw.lower()
        for idx, label in enumerate(low_index):
            if kwl in label: return df.index[idx]
    return None

def _get_val(df, keywords):
    """Get the first value from a row matching keywords."""
    r = _find_first_row(df, keywords)
    if r:
        vals = df.loc[r].dropna().astype(float).values
        if len(vals) > 0: return float(vals[0])
    return 0.0

def _latest_and_prior(df, keywords):
    """Return (latest, prior) values from a pandas Series."""
    r = _find_first_row(df, keywords)
    if r:
        vals = df.loc[r].dropna().astype(float).values
        if len(vals) >= 2: return (vals[0], vals[1])
        if len(vals) == 1: return (vals[0], None)
    return (None, None)


# --- 1. Core Data Extraction ---

def compute_fundamental_ratios(stock_obj):
    """
    Extracts ROE, Debt, FCF, and Growth using robust fallbacks.
    """
    ratios = {
        "roe": 0.0, "debt_to_equity": 0.0, "free_cash_flow": 0.0, "revenue_growth": 0.0,
        "market_cap": 0.0, "pe_ratio": 0.0, "eps": 0.0, "beta": 0.0, "dividend_yield": 0.0,
        "interest_coverage": 100.0, "pledge_pct": 0.0
    }

    try:
        fast = stock_obj.fast_info
        info = stock_obj.info
        fin = stock_obj.financials
        bs = stock_obj.balance_sheet
        cf = stock_obj.cashflow

        # Basic Stats
        try:
            # TRY FAST_INFO (Realtime) -> THEN INFO (Cached)
            mc = fast.get("market_cap")
            if mc is None: mc = info.get("marketCap")
            ratios["market_cap"] = float(mc or 0)
            
            ratios["pe_ratio"] = float(info.get("trailingPE") or 0)
            ratios["eps"] = float(info.get("trailingEps") or 0)
            ratios["beta"] = float(info.get("beta") or 0)
            ratios["dividend_yield"] = float(info.get("dividendYield") or 0)
        except: pass

        # ROE (Net Income / Equity)
        net_income = _get_val(fin, ["Net Income", "Net Income Common Stockholders"])
        total_equity = _get_val(bs, ["Total Stockholder Equity", "Total Equity", "Stockholders Equity"])
        if net_income and total_equity:
            ratios["roe"] = float(net_income / total_equity)

        # Debt to Equity
        total_debt = _get_val(bs, ["Total Debt", "Long Term Debt"])
        if 'totalDebt' in fast: total_debt = fast['totalDebt']
        
        if total_debt and total_equity:
            ratios["debt_to_equity"] = float(total_debt / total_equity)

        # Free Cash Flow (OCF + CapEx)
        ocf = _get_val(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"])
        capex = _get_val(cf, ["Capital Expenditures"])
        # CapEx is usually negative, so we add it
        if ocf:
            ratios["free_cash_flow"] = float(ocf + capex)
        elif 'freeCashflow' in info:
             ratios["free_cash_flow"] = float(info['freeCashflow'])

        # Revenue Growth
        rev_now, rev_prev = _latest_and_prior(fin, ["Total Revenue", "Revenue"])
        if rev_now and rev_prev and rev_prev != 0:
            ratios["revenue_growth"] = float((rev_now - rev_prev) / rev_prev)
        elif 'revenueGrowth' in info:
             ratios["revenue_growth"] = float(info['revenueGrowth'])

    
        # Interest Coverage Ratio (EBIT / Interest Expense)
        ebit = _get_val(fin, ["EBIT", "Operating Income"])
        interest_expense = _get_val(fin, ["Interest Expense", "InterestMetrics"]) 
        # Note: Interest Expense is usually negative in financials
        if ebit and interest_expense:
             ratios["interest_coverage"] = float(ebit / abs(interest_expense))
        
        # Pledge Percentage (Placeholder - Data not easily available in free YF)
        # We try to look for 'heldPercentPledged' in info if it ever exists, or use 'sharesPercentSharesOut' as a very rough proxy if named suspiciously?
        # For now, we default to 0.0 unless we find a specific key.
        if 'heldPercentPledged' in info:
             ratios["pledge_pct"] = float(info['heldPercentPledged'])
        
    except Exception as e:
        print(f"ASTRA: Fundamental Calc Warning: {e}")
    
    return ratios


# --- 2. Advanced Risk Models (Piotroski & Altman) ---

def calculate_piotroski_f_score(stock_obj):
    """Calculates Piotroski F-Score (0-9)."""
    score = 0
    try:
        fin = stock_obj.financials
        bal = stock_obj.balance_sheet
        cf = stock_obj.cashflow
        if fin.empty or bal.empty: return 5 # Neutral default
        
        ni_now, ni_prev = _latest_and_prior(fin, ["Net Income"])
        ta_now, ta_prev = _latest_and_prior(bal, ["Total Assets"])
        cfo_now, _ = _latest_and_prior(cf, ["Operating Cash Flow"])
        ltd_now, ltd_prev = _latest_and_prior(bal, ["Long Term Debt", "Total Debt"])
        
        # Profitability
        if ni_now and ni_now > 0: score += 1
        if cfo_now and cfo_now > 0: score += 1
        if ni_now and ta_now and ni_prev and ta_prev and (ni_now/ta_now) > (ni_prev/ta_prev): score += 1
        if cfo_now and ni_now and cfo_now > ni_now: score += 1
        
        # Leverage
        if ltd_now is not None and ltd_prev is not None and ltd_now < ltd_prev: score += 1
        elif ltd_now is None: score += 1
        
        # Efficiency (simplified)
        gm_now, gm_prev = _latest_and_prior(fin, ["Gross Profit"])
        rev_now, rev_prev = _latest_and_prior(fin, ["Total Revenue"])
        if gm_now and rev_now and gm_prev and rev_prev:
            if (gm_now/rev_now) > (gm_prev/rev_prev): score += 1
            
        return score
    except: return 5

def altman_z_score(fin, bal, market_cap):
    """Calculates Altman Z-Score (Bankruptcy Risk)."""
    try:
        ta = _get_val(bal, ["Total Assets"])
        tl = _get_val(bal, ["Total Liabilities"])
        ca = _get_val(bal, ["Total Current Assets"])
        cl = _get_val(bal, ["Total Current Liabilities"])
        re = _get_val(bal, ["Retained Earnings"])
        ebit = _get_val(fin, ["EBIT", "Operating Income"])
        sales = _get_val(fin, ["Total Revenue"])
        
        if not ta or ta == 0: return 1.8 # Grey Zone default (instead of safe 3.0)
        
        wc = ca - cl
        A = wc / ta
        B = re / ta
        C = ebit / ta
        D = market_cap / (tl if tl else 1)
        E = sales / ta
        
        z = (1.2*A) + (1.4*B) + (3.3*C) + (0.6*D) + (1.0*E)
        return float(z)
    except: return 1.8

def beneish_m_score(fin, bal, cf):
    """
    Simplified Beneish M-Score (Fraud Detection).
    Focuses on core manipulation signals: Days Sales in Receivables & Gross Margin.
    Full 8-variable model is often data-constrained on free APIs.
    """
    try:
        # DSRI: Days Sales in Receivables Index
        rec_now, rec_prev = _latest_and_prior(bal, ["Net Receivables", "Accounts Receivable"])
        rev_now, rev_prev = _latest_and_prior(fin, ["Total Revenue", "Revenue"])
        
        dsri = 1.0
        if rev_now and rev_prev and rec_now and rec_prev:
            dsri = (rec_now / rev_now) / (rec_prev / rev_prev)

        # GMI: Gross Margin Index (worsening margins is a risk)
        gm_now, gm_prev = _latest_and_prior(fin, ["Gross Profit"])
        gmi = 1.0
        if gm_now and gm_prev and rev_now and rev_prev:
             margin_now = gm_now / rev_now
             margin_prev = gm_prev / rev_prev
             gmi = margin_prev / margin_now # Inverted: deterioration > 1
        
        # Simplified Formula (Proxy)
        # M = -4.84 + 0.92*DSRI + 0.528*GMI ...
        m_score = -4.84 + (0.92 * dsri) + (0.528 * gmi)
        
        return float(m_score)
    except:
        return -1.78 # Borderline default (instead of safe -2.5)

# --- 3. Scoring Functions ---

def score_fundamentals(r):
    """Calculates 0-100 score based on raw ratios."""
    score = 0.0
    weights = 0.0

    # ROE
    if r['roe'] != 0:
        weights += 1
        score += min(max(r['roe'] * 100, 0), 20)

    # Debt
    weights += 1
    score += max(0, 20 - min(r['debt_to_equity'] * 10, 20))

    # Growth
    if r['revenue_growth'] != 0:
        weights += 1
        if r['revenue_growth'] > 0.20: score += 20
        elif r['revenue_growth'] > 0.10: score += 15
        elif r['revenue_growth'] > 0.05: score += 10

    # Dividend Yield
    if r.get('dividend_yield', 0) > 0:
        weights += 1
        yield_val = r['dividend_yield']
        if yield_val > 0.04: score += 20
        elif yield_val > 0.02: score += 15
        else: score += 10
        
    # PE Ration (Valuation)
    pe = r.get('pe_ratio', 0)
    if pe > 0:
        weights += 1
        if pe < 15: score += 20     # Deep Value
        elif pe < 25: score += 15   # Fair Value
        elif pe < 40: score += 10   # Growth
        else: score += 5           # Expensive
        
    if weights == 0: return 50.0
    return min(100.0, (score / (weights * 20.0)) * 100.0)

def get_fundamental_score(ratios, risk_metrics):
    """Combines Ratios + Risk Metrics into a composite score."""
    base_score = score_fundamentals(ratios)
    f_score = risk_metrics.get('f_score', 5)
    z_score = risk_metrics.get('z_score', 3)
    m_score = risk_metrics.get('m_score', -2.5)
    
    # Boost score for High Quality
    if f_score >= 7: base_score += 10
    elif f_score <= 3: base_score -= 10
    
    if z_score > 3: base_score += 5
    elif z_score < 1.8: base_score -= 20
    
    if m_score > -1.78: base_score -= 25 # High fraud probability penalty
    
    return max(0, min(100, base_score))

def get_risk_score(ratios, risk_metrics):
    """Returns 0-100 Risk Score (Higher is Safer)."""
    score = 50.0
    de = ratios.get('debt_to_equity', 0)
    if de < 0.5: score += 20
    elif de > 2.0: score -= 20
    
    z = risk_metrics.get('z_score', 3)
    if z > 3: score += 15
    elif z < 1.8: score -= 25
    
    m = risk_metrics.get('m_score', -2.5)
    if m > -1.78: score -= 25
    
    
    # Task 1.2: Integrity Shield Penalties
    pledge = ratios.get('pledge_pct', 0)
    icr = ratios.get('interest_coverage', 100)
    
    if pledge > 0.25: score -= 30 # Governance Red Flag
    if icr < 1.5: score -= 20 # Solvency Risk
    
    return max(0, min(100, score))
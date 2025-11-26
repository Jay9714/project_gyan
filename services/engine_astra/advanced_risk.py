import pandas as pd
import numpy as np

def _find_value(df, keywords):
    """Helper to find a value in a financial dataframe using keywords."""
    if df.empty: return None
    for kw in keywords:
        matches = [idx for idx in df.index if kw.lower() in str(idx).lower()]
        if matches:
            row = df.loc[matches[0]]
            #Return first non-NaN value
            vals = row.dropna().values
            if len(vals) > 0: return float(vals[0])
    return None

def _get_latest_prior(df, keywords):
    """Returns (latest, prior) values for a row matching keywords."""
    if df.empty: return (None, None)
    for kw in keywords:
        matches = [idx for idx in df.index if kw.lower() in str(idx).lower()]
        if matches:
            row = df.loc[matches[0]]
            vals = row.dropna().astype(float).values
            if len(vals) >= 2: return (vals[0], vals[1])
            if len(vals) == 1: return (vals[0], None)
    return (None, None)

def calculate_piotroski_f_score(ticker_obj):
    """Calculates Piotroski F-Score (0-9)."""
    score = 0
    try:
        fin = ticker_obj.financials
        bal = ticker_obj.balance_sheet
        cf = ticker_obj.cashflow
        
        if fin.empty or bal.empty or cf.empty: return 5 # Neutral default

        # 1. Profitability
        ni_now, ni_prev = _get_latest_prior(fin, ["Net Income", "Net Income Common Stockholders"])
        ta_now, ta_prev = _get_latest_prior(bal, ["Total Assets"])
        cfo_now, _ = _get_latest_prior(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"])

        if ni_now and ni_now > 0: score += 1 # Positive NI
        if cfo_now and cfo_now > 0: score += 1 # Positive CFO
        
        # ROA Improvement
        if ni_now and ta_now and ni_prev and ta_prev:
            if (ni_now/ta_now) > (ni_prev/ta_prev): score += 1
            
        # Quality of Earnings (CFO > NI)
        if cfo_now and ni_now and cfo_now > ni_now: score += 1

        # 2. Leverage / Liquidity
        ltd_now, ltd_prev = _get_latest_prior(bal, ["Long Term Debt", "Total Debt"])
        if ltd_now is not None and ltd_prev is not None: # Lower Debt
             if ltd_now < ltd_prev: score += 1
        elif ltd_now is None: score += 1 # No debt is good

        curr_assets_now, curr_assets_prev = _get_latest_prior(bal, ["Total Current Assets"])
        curr_liab_now, curr_liab_prev = _get_latest_prior(bal, ["Total Current Liabilities"])
        
        if curr_assets_now and curr_liab_now and curr_assets_prev and curr_liab_prev:
            current_ratio_now = curr_assets_now / curr_liab_now
            current_ratio_prev = curr_assets_prev / curr_liab_prev
            if current_ratio_now > current_ratio_prev: score += 1 # Liquidity improved

        # Shares (Dilution)
        shares_now, shares_prev = _get_latest_prior(bal, ["Ordinary Shares Number", "Share Issued"])
        if shares_now and shares_prev and shares_now <= shares_prev: score += 1

        # 3. Operating Efficiency
        gm_now, gm_prev = _get_latest_prior(fin, ["Gross Profit"])
        rev_now, rev_prev = _get_latest_prior(fin, ["Total Revenue"])
        
        if gm_now and rev_now and gm_prev and rev_prev:
            margin_now = gm_now / rev_now
            margin_prev = gm_prev / rev_prev
            if margin_now > margin_prev: score += 1 # Gross Margin improved
            
            turnover_now = rev_now / ta_now
            turnover_prev = rev_prev / ta_prev
            if turnover_now > turnover_prev: score += 1 # Asset Turnover improved

        return score
    except:
        return 5

def calculate_altman_z_score(ticker_obj, market_cap):
    """Calculates Altman Z-Score for Bankruptcy Risk."""
    try:
        bal = ticker_obj.balance_sheet
        fin = ticker_obj.financials
        
        if bal.empty or fin.empty: return 3.0

        # Variables
        ta = _find_value(bal, ["Total Assets"])
        tl = _find_value(bal, ["Total Liabilities Net Minority Interest", "Total Liabilities"])
        ca = _find_value(bal, ["Total Current Assets"])
        cl = _find_value(bal, ["Total Current Liabilities"])
        re = _find_value(bal, ["Retained Earnings"])
        ebit = _find_value(fin, ["EBIT", "Operating Income"])
        sales = _find_value(fin, ["Total Revenue"])
        
        if not ta or ta == 0: return 3.0
        
        wc = (ca - cl) if (ca and cl) else 0
        
        # Ratios
        A = wc / ta
        B = (re or 0) / ta
        C = (ebit or 0) / ta
        D = (market_cap or 0) / (tl or 1) # Market Value of Equity / Total Liabilities
        E = (sales or 0) / ta
        
        # Formula (Public Manufacturing/General)
        z_score = (1.2 * A) + (1.4 * B) + (3.3 * C) + (0.6 * D) + (1.0 * E)
        return round(z_score, 2)
    except:
        return 3.0
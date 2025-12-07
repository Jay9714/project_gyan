import pandas as pd
import numpy as np
import yfinance as yf
from pypfopt import EfficientFrontier
from pypfopt import risk_models
from pypfopt import expected_returns
from pypfopt.discrete_allocation import DiscreteAllocation, get_latest_prices

def get_portfolio_optimization(holdings_list, total_investment_value):
    """
    Optimizes the portfolio using Mean-Variance Optimization (Markowitz).
    Returns suggested quantity adjustments.
    """
    if not holdings_list:
        return {}

    # 1. Extract tickers
    tickers = [item['ticker'] for item in holdings_list]
    if len(tickers) < 2:
        return {"error": "Need at least 2 stocks to optimize."}

    # 2. Fetch Historical Data (1 Year)
    try:
        # Download all at once
        data = yf.download(tickers, period="1y")['Close']
    except Exception as e:
        return {"error": f"Failed to fetch data: {str(e)}"}

    if data.empty:
        return {"error": "No data found for tickers."}
        
    # Drop columns with too many NaNs
    data = data.dropna(axis=1, how='all').dropna()

    if data.shape[1] < 2:
         return {"error": "Insufficient valid data for optimization."}

    # 3. Calculate Expected Returns and Sample Covariance
    #    - Mean Historical Return
    #    - Risk Models (Ledoit-Wolf is robust)
    mu = expected_returns.mean_historical_return(data)
    S = risk_models.sample_cov(data)

    # 4. Optimize for Maximum Sharpe Ratio (Risk-Adjusted Return)
    ef = EfficientFrontier(mu, S)
    
    try:
        weights = ef.max_sharpe()
        cleaned_weights = ef.clean_weights()
    except:
        # Fallback if Max Sharpe fails (e.g., all returns negative)
        weights = ef.min_volatility()
        cleaned_weights = ef.clean_weights()

    # 5. Convert weights to specific quantities (Allocation)
    #    latest_prices = get_latest_prices(data)
    latest_prices = data.iloc[-1]
    
    da = DiscreteAllocation(cleaned_weights, latest_prices, total_portfolio_value=total_investment_value)
    allocation, leftover = da.greedy_portfolio()
    
    # 6. Format Output
    # Compare current qty vs suggested qty
    suggestion = []
    
    for ticker, qty in allocation.items():
        current_qty = next((x['quantity'] for x in holdings_list if x['ticker'] == ticker), 0)
        action = "HOLD"
        diff = qty - current_qty
        
        if diff > 0: action = f"BUY {diff}"
        elif diff < 0: action = f"SELL {abs(diff)}"
        
        suggestion.append({
            "ticker": ticker,
            "current_qty": current_qty,
            "suggested_qty": qty,
            "action": action,
            "weight": round(cleaned_weights.get(ticker, 0) * 100, 1)
        })
        
    # Sort by weight
    suggestion.sort(key=lambda x: x['weight'], reverse=True)
    
    return {
        "optimization_type": "Max Sharpe Ratio",
        "suggestions": suggestion,
        "performance": ef.portfolio_performance(verbose=False)
    }
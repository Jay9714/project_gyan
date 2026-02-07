import math

# Task 1.1: Enhanced Cost Engine
# Supports Equity, Options, Futures, Commodities (MCX), Indices.

def calculate_transaction_costs(price, quantity, side, instrument_type="EQUITY_INTRADAY"):
    """
    Calculate transaction costs including Brokerage, STT/CTT, Exchange Charges, GST, and SEBI Charges.
    
    Args:
        price (float): Execution price per unit.
        quantity (int): Number of units.
        side (str): "BUY" or "SELL".
        instrument_type (str): Options: "EQUITY_INTRADAY", "EQUITY_DELIVERY", "FUTURES", "OPTIONS", 
                                "COMMODITY_FUTURES" (MCX), "COMMODITY_OPTIONS", "CURRENCY_FUTURES".
        
    Returns:
        float: Total transaction cost in INR.
    """
    turnover = price * quantity
    
    # 1. Brokerage (Shoonya = 0, others typically ₹20/order)
    # We stick to Shoonya (0) as per prompt, but logic is extensible.
    brokerage = 0.0
    
    # 2. STT / CTT (Security/Commodity Transaction Tax)
    # Rates updated as of 2024-25 standards
    tax = 0.0
    
    if instrument_type == "EQUITY_INTRADAY":
        # 0.025% on SELL only
        if side.upper() == "SELL":
            tax = turnover * 0.00025
            
    elif instrument_type == "EQUITY_DELIVERY":
        # 0.1% on BUY and SELL
        tax = turnover * 0.001
        
    elif instrument_type == "FUTURES":
        # 0.0125% on SELL only
        if side.upper() == "SELL":
            tax = turnover * 0.000125
            
    elif instrument_type == "OPTIONS":
        # 0.0625% on SELL side PREMIUM (Turnover)
        if side.upper() == "SELL":
            tax = turnover * 0.000625

    elif instrument_type == "COMMODITY_FUTURES": # MCX
        # CTT: 0.01% on SELL (Non-Agri)
        if side.upper() == "SELL":
            tax = turnover * 0.0001
            
    elif instrument_type == "COMMODITY_OPTIONS":
        # CTT: 0.05% on SELL
        if side.upper() == "SELL":
            tax = turnover * 0.0005

    elif instrument_type == "CURRENCY_FUTURES":
        # No STT/CTT usually
        tax = 0.0
            
    # 3. Exchange Transaction Charges (NSE/MCX approx)
    exch_charge = 0.0
    
    if "EQUITY" in instrument_type:
        exch_charge = turnover * 0.0000325 # NSE: 0.00325%
    elif instrument_type == "FUTURES":
        exch_charge = turnover * 0.000019 # NSE: 0.0019%
    elif instrument_type == "OPTIONS":
        exch_charge = turnover * 0.00053  # NSE: 0.053% (on premium)
    elif "COMMODITY" in instrument_type:
        exch_charge = turnover * 0.000015 # MCX (varies, approx 0.0015%)
    elif "CURRENCY" in instrument_type:
        exch_charge = turnover * 0.000009 # NSE Currency
        
    # 4. GST (18% on Brokerage + Exchange Charges)
    gst = (brokerage + exch_charge) * 0.18
    
    # 5. SEBI Charges (₹10 per crore = 0.0001%)
    sebi_charges = turnover * 0.000001
    
    # 6. Stamp Duty (State wise, taking standard distinct values)
    # Buy side only usually
    stamp_duty = 0.0
    if side.upper() == "BUY":
        if instrument_type == "EQUITY_DELIVERY": 
            stamp_duty = turnover * 0.00015 # 0.015%
        elif instrument_type == "EQUITY_INTRADAY":
            stamp_duty = turnover * 0.00003 # 0.003%
        elif "FUTURES" in instrument_type:
            stamp_duty = turnover * 0.00002 # 0.002%
        elif "OPTIONS" in instrument_type:
            stamp_duty = turnover * 0.00003 # 0.003%

    total_cost = brokerage + tax + exch_charge + gst + sebi_charges + stamp_duty
    return round(total_cost, 2)

def filter_feasible_instruments(capital, ticker):
    """
    AI Hook: Filters instruments based on capital.
    Simple logic for now, can be replaced by LLM.
    """
    feasible = []
    
    # Equity Intraday always feasible if capital > 500
    if capital > 500:
        feasible.append("EQUITY_INTRADAY")
        
    # Options require lot size margin (approx 50k - 1L for selling, 5k-10k for buying)
    # We assume 'Trade' means buying for simplicity, but selling needs more.
    if capital > 20000:
        feasible.append("OPTIONS_BUY")
    
    if capital > 150000:
        feasible.append("OPTIONS_SELL")
        feasible.append("FUTURES")
        
    if "GOLD" in ticker or "CRUDE" in ticker:
        if capital > 10000: feasible.append("COMMODITY_FUTURES")
        
    return feasible

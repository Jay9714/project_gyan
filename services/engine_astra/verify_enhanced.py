
import sys
import os

print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")

try:
    print("----- VERIFICATION START (Inside Astra Brain) -----")
    
    print("1. Testing Costs...")
    # 'shared' is mounted at /app/shared
    # So 'import shared.costs' should work if /app is in path (it is)
    from shared.costs import calculate_transaction_costs, filter_feasible_instruments
    c = calculate_transaction_costs(100, 10, "BUY", "EQUITY_INTRADAY")
    print(f"   Cost (Equity): {c}")
    c2 = calculate_transaction_costs(25000, 1, "SELL", "MCX_FUTURES") 
    print(f"   Cost (MCX/Future check): {c2}")
    
    print("2. Testing Strategy Registry...")
    # In /app, strategy_registry.py is local
    from strategy_registry import StrategyRegistry
    sr = StrategyRegistry()
    func = sr.get_strategy("HIGH_VOL_CRASH")
    print(f"   Strategy for Crash: {func.__name__}")
    
    print("3. Testing Market Regime...")
    from market_regime import detect_market_regime
    # Mocking call or just import check
    print(f"   Regime detection import successful (Function: {detect_market_regime.__name__})")
    
    print("4. Testing Config Selector...")
    from config_selector import config_selector
    conf = config_selector.select_config("BULL_TREND", 200000, "POSITIVE")
    print(f"   Selected Config: {conf}")
    
    print("5. Testing Risk Manager...")
    from risk_manager import risk_manager
    allowed, reas = risk_manager.check_entry_allowance(90000, 100000, -3000)
    print(f"   Risk Check (-3% daily): {allowed} ({reas})")
    
    print("6. Testing Trade Schema...")
    from shared.database import Trade
    t = Trade(ticker="TEST", instrument_type="OPTIONS")
    print(f"   Trade Instance created: {t}")

    print("----- VERIFICATION PASSED -----")

except Exception as e:
    print(f"!!!!! VERIFICATION FAILED: {e}")
    import traceback
    traceback.print_exc()

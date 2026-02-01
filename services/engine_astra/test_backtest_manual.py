
import sys
import os
import types
from unittest.mock import MagicMock
import pandas as pd
import numpy as np

# --- MOCKING MODULES ---

# Mock vectorbt
vbt_mock = types.ModuleType("vectorbt")
portfolio_mock = MagicMock()
portfolio_mock.total_return.return_value = 0.15
portfolio_mock.total_benchmark_return.return_value = 0.10
portfolio_mock.sharpe_ratio.return_value = 1.5
portfolio_mock.sortino_ratio.return_value = 2.0
portfolio_mock.max_drawdown.return_value = -0.05
portfolio_mock.trades.win_rate.return_value = 0.60
portfolio_mock.trades.count.return_value = 12

vbt_mock.Portfolio = MagicMock()
vbt_mock.Portfolio.from_signals.return_value = portfolio_mock
sys.modules["vectorbt"] = vbt_mock

# Mock catboost, lightgbm, darts (so ai_models imports don't fail)
sys.modules["catboost"] = MagicMock()
sys.modules["lightgbm"] = MagicMock()
sys.modules["darts"] = MagicMock()
sys.modules["darts.models"] = MagicMock()

# Mock prophet
sys.modules["prophet"] = MagicMock()

# Mock xgboost
sys.modules["xgboost"] = MagicMock()

# Mock sklearn
sys.modules["sklearn"] = MagicMock()
sys.modules["sklearn.ensemble"] = MagicMock()
sys.modules["sklearn.linear_model"] = MagicMock()
sys.modules["sklearn.model_selection"] = MagicMock()
sys.modules["sklearn.metrics"] = MagicMock()

# Mock ta (if missing)
ta_mock = MagicMock()
sys.modules["ta"] = ta_mock
sys.modules["ta.trend"] = MagicMock()
sys.modules["ta.momentum"] = MagicMock()
sys.modules["ta.volatility"] = MagicMock()

# --- END MOCKS ---

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# We need to manually patch ai_models to avoid real imports if they happen inside functions or top level
# But since we mocked the libs above, importing ai_models should be fine.
# However, BacktestEngine.run calls train_ensemble_model. We should mock that function specifically
# to avoid waiting for training or errors.

import services.engine_astra.backtest_engine as be
from services.engine_astra.backtest_engine import BacktestEngine
import logging

# Patch train_ensemble_model and load_model
be.train_ensemble_model = MagicMock(return_value=0.05)
mock_model = MagicMock()
mock_model.predict.return_value = np.random.uniform(-0.02, 0.02, 500) # Dummy preds
be.load_model = MagicMock(return_value=mock_model)

# Patch add_ta_features to avoid 'ta' library dependency issues and return dummy features
def mock_add_ta_features(df):
    df['rsi'] = 50.0
    df['momentum_7'] = 0.01
    df['atr'] = 1.0
    df['close_lag_1'] = df['Close']
    df['vol_rel'] = 1.0
    df['dist_ema'] = 0.0
    df['atr_pct'] = 0.01
    return df

# We need to patch where BacktestEngine imports it. 
# It imports `from technical_analysis import add_ta_features`
# So we check `be.add_ta_features`
be.add_ta_features = mock_add_ta_features

logging.basicConfig(level=logging.INFO)

def main():
    ticker = "TCS.NS"
    start_date = "2024-01-01"
    end_date = "2024-12-31"
    
    print(f"Running MOCKED backtest for {ticker} from {start_date} to {end_date}...")
    
    # We also need to mock yfinance if network is issue, but let's try real fetch first.
    # If fetch fails, we can mock it too.
    
    engine = BacktestEngine(ticker)
    
    # 1. Fetch Data
    # If yfinance isn't installed/working, this will fail.
    # But let's assume yf is there (it usually installs fast).
    if not engine.fetch_data():
        print("Failed to fetch data (Check network/yfinance).")
        return

    # 2. Run Backtest
    results = engine.run(start_date, end_date)
    
    if results:
        print("\n✅ VBT Mock Backtest Successful!")
        print("Results Summary:")
        for k, v in results.items():
            print(f"  {k}: {v}")
            
        # Verify specific values from mock
        if results['Sharpe Ratio'] == 1.5:
             print("✅ Sharpe Ratio verified correctly from VectorBT integration.")
    else:
        print("\n❌ Backtest Failed.")

if __name__ == "__main__":
    main()

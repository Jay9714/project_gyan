import sys
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
import numpy as np

# Add path to find local modules
sys.path.append("/app")

from technical_analysis import add_ta_features
from ai_models import train_ensemble_model, ENSEMBLE_FEATURES

def run_backtest_scenario(ticker, cutoff_date_str):
    print(f"\n🧪 --- BACKTEST SIMULATION: {ticker} starting from {cutoff_date_str} ---")
    
    # 1. Fetch Data (Enough to cover the past + 7 days after cutoff)
    print("1️⃣  Fetching full historical data...")
    try:
        t = yf.Ticker(ticker)
        df = t.history(period="2y", interval="1d")
        if df.empty:
            print("❌ No data found.")
            return
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
        return

    # 2. Feature Engineering (Calculate indicators on full history first)
    # This ensures valid Moving Averages (e.g. 200-day EMA) for the cutoff date
    df = add_ta_features(df)
    ai_df = df.reset_index().rename(columns={
        'Date':'date', 'Close':'close', 'Volume':'volume',
        'Open':'open', 'High':'high', 'Low':'low'
    })
    
    # Ensure date is timezone-naive
    if pd.api.types.is_datetime64_any_dtype(ai_df['date']):
        ai_df['date'] = ai_df['date'].dt.tz_localize(None)
    
    cutoff_dt = pd.to_datetime(cutoff_date_str)
    
    # 3. SPLIT DATA: The "Wall of Time"
    # TRAIN: All history strictly BEFORE the cutoff date
    train_df = ai_df[ai_df['date'] < cutoff_dt].copy()
    
    # TEST: The 7 days STARTING from cutoff date (The "Future")
    future_df = ai_df[ai_df['date'] >= cutoff_dt].head(7).copy()
    
    if len(train_df) < 200:
        print("❌ Not enough historical data before this date to train reliably.")
        return
        
    if len(future_df) == 0:
        print(f"❌ No data found after {cutoff_date_str}. (Is it a weekend or holiday?)")
        return

    print(f"2️⃣  Training AI using data up to {train_df['date'].iloc[-1].date()}...")
    print(f"    (The AI is BLIND to anything after this date)")
    
    # 4. Train the Model on PAST data only
    # horizon=1 means it learns to predict T+1 from T
    stack_model, _ = train_ensemble_model(train_df, ticker, horizon=1)
    
    if not stack_model:
        print("❌ Training failed.")
        return

    # 5. Run the Simulation Day-by-Day
    print("\n3️⃣  Simulating the next 7 Days (Predicting Returns)...")
    print("-" * 85)
    print(f"{'Date':<12} | {'Actual Price':<12} | {'AI Prediction':<12} | {'Diff':<10} | {'Status':<10}")
    print("-" * 85)
    
    features = [f for f in ENSEMBLE_FEATURES if f in ai_df.columns]
    
    for i in range(len(future_df)):
        row = future_df.iloc[[i]] # The day we are predicting (e.g., Jan 11)
        target_date = row['date'].dt.strftime('%Y-%m-%d').item()
        real_price = row['close'].item()
        
        # To predict Jan 11, we must use features from Jan 10
        # Find the row index in the full dataframe
        current_idx = row.index.item()
        if current_idx == 0: continue
        
        # Get PREVIOUS day's data (The input for the prediction)
        prev_row = ai_df.loc[[current_idx - 1]][features].fillna(0)
        prev_close = ai_df.loc[current_idx - 1, 'close']
        
        # --- FIX: Convert Return Prediction to Price ---
        pred_return = float(stack_model.predict(prev_row)[0])
        pred_price = prev_close * (1 + pred_return)
        # -----------------------------------------------
        
        # Calculate Accuracy
        diff = pred_price - real_price
        error_pct = abs(diff / real_price) * 100
        
        status = "✅ HIT" if error_pct < 2.0 else "⚠️ MISS"
        if error_pct > 5.0: status = "❌ FAIL"
        
        print(f"{target_date:<12} | ₹{real_price:<11.2f} | ₹{pred_price:<11.2f} | {diff:<+10.2f} | {status}")

    print("-" * 85)
    print("\n✅ Simulation Complete.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python backtest_scenario.py <TICKER> <DATE>")
        # Default fallback for testing
        run_backtest_scenario("RELIANCE.NS", "2024-11-01") 
    else:
        run_backtest_scenario(sys.argv[1], sys.argv[2])
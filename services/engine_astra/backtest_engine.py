
import pandas as pd
import yfinance as yf
from datetime import timedelta
import numpy as np

# Local Imports
from technical_analysis import add_ta_features
from ai_models import train_ensemble_model, load_model, ENSEMBLE_FEATURES

class BacktestEngine:
    def __init__(self, ticker):
        self.ticker = ticker
        self.df = None
        self.results = []
        self.model = None
        self.model_date = None

    def fetch_data(self):
        """Fetches 2 years of data to ensure enough history for indicators."""
        print(f"🔄 Fetching data for {self.ticker}...")
        try:
            # DEBUG: Print timezone info
            import datetime
            print(f"   Current Time: {datetime.datetime.now()}")
            
            print(f"   Ticker: {repr(self.ticker)}")
            
            t = yf.Ticker(self.ticker)
            raw_df = t.history(period="5y", interval="1d")
            
            print(f"   Raw DF Shape (Before TA): {raw_df.shape}")
            if raw_df.empty:
                print(f"❌ No data for {self.ticker}")
                return False
            
            df = add_ta_features(raw_df)
            print(f"   DF Shape (After TA): {df.shape}")
            if df.empty:
                print("❌ DF became empty after Technical Analysis (Check dropna?)")
                return False
                
            self.df = df.reset_index().rename(columns={
                'Date':'date', 'Close':'close', 'Volume':'volume',
                'Open':'open', 'High':'high', 'Low':'low'
            })
            
            # --- ROBUST DATE NORMALIZATION ---
            try:
                # 1. Force Datetime (UTC)
                self.df['date'] = pd.to_datetime(self.df['date'], utc=True)
                # 2. Convert to Naive (remove timezone info)
                self.df['date'] = self.df['date'].dt.tz_localize(None)
            except Exception as e:
                print(f"❌ Date Normalization Error: {e}")
                return False
            # ---------------------------------
                
            return True
        except Exception as e:
            print(f"❌ Error fetching data: {e}")
            return False

    def run(self, start_date, end_date):
        """
        Walk-Forward Simulation.
        """
        if self.df is None:
            if not self.fetch_data(): return

        print(f"🧪 Running Backtest from {start_date} to {end_date}...")
        
        # Robust Start Filter
        start_dt = pd.to_datetime(start_date)
        if start_dt.tzinfo: start_dt = start_dt.tz_localize(None)
        
        end_dt = pd.to_datetime(end_date)
        if end_dt.tzinfo: end_dt = end_dt.tz_localize(None)

        # Filter for the simulation window + lookback for features
        # We need the loop to start at start_date
        sim_dates = self.df[(self.df['date'] >= start_dt) & 
                            (self.df['date'] <= end_dt)]['date'].tolist()

        if not sim_dates:
            print(f"❌ No trading days found in range {start_date} to {end_date}.")
            if not self.df.empty:
               print(f"   Input Start Date: {start_date} (Type: {type(start_date)})")
               print(f"   DF Date Column: {self.df['date'].head()}")
               print(f"   DF Filter Check: {pd.to_datetime(start_date)}")
               mask = (self.df['date'] >= pd.to_datetime(start_date))
               print(f"   Rows matching start date: {mask.sum()}")
            return

        for current_date in sim_dates:
            self._process_day(current_date)

        return pd.DataFrame(self.results)

    def _process_day(self, current_date):
        # 1. POINT-IN-TIME Slicing
        # We pretend today is 'current_date'. We strictly CANNOT see row of current_date
        # or anything after it for TRAINING. 
        # But we need row of 'current_date' to make a prediction FOR (at market open) 
        # or compare AGAINST (at market close).
        
        # Let's say we are closely after market close on current_date.
        # We have data UP TO current_date.
        # We want to predict current_date+1 ? 
        # OR we are at current_date open and want to predict current_date close?
        
        # Standard: At Day T Close, Predict Day T+1 Return.
        
        mask_history = self.df['date'] < current_date
        train_df = self.df[mask_history].copy()
        
        if len(train_df) < 200: return # Warmup needed
        
        # 2. Retrain Strategy (Weekly)
        # Retraining every day is too slow. Let's retrain on Mondays.
        is_monday = current_date.weekday() == 0
        if self.model is None or is_monday:
            # print(f"   training model on data up to {train_df['date'].iloc[-1].date()}...")
            try:
                # We interpret horizon=1 as predicting T+1
                # Phase 1 Change: train_ensemble_model returns RMSE, not (model, metrics)
                # It saves the model to disk.
                rmse = train_ensemble_model(train_df, self.ticker, horizon=1)
                
                # Load the model back from disk to use it
                self.model = load_model(self.ticker, 'ensemble')
                self.model_date = current_date
            except Exception as e:
                print(f"   ⚠️ Training failed on {current_date.date()}: {e}")
                import traceback
                traceback.print_exc()
                return

        if not self.model: return

        # 3. Predict for Current Date (using yesterday's data)
        # We want to know: "If I acted yesterday, would I be right today?"
        # OR "What is my prediction for tomorrow?"
        
        # Let's assess: At T-1 Close, we predicted T Close.
        # So we look at T-1 attributes.
        
        # Find index of current_date
        curr_idx = self.df.index[self.df['date'] == current_date].tolist()[0]
        if curr_idx == 0: return
        
        prev_row = self.df.iloc[[curr_idx - 1]]
        
        # Extract features for prediction
        # features_row = prev_row[ENSEMBLE_FEATURES].fillna(0) # This needs to match exactly what train expects
        # The ENSEMBLE_FEATURES are defined in ai_models.py (I need to import them)
        features_to_use = [f for f in ENSEMBLE_FEATURES if f in self.df.columns]
        input_data = prev_row[features_to_use].fillna(0)
        
        try:
            pred_return = float(self.model.predict(input_data)[0])
        except:
            return

        # 4. Evaluate
        actual_close = self.df.loc[curr_idx, 'close']
        prev_close = self.df.loc[curr_idx - 1, 'close']
        actual_return = (actual_close - prev_close) / prev_close
        
        pred_price = prev_close * (1 + pred_return)
        
        # Debug Model Output
        # print(f"   Date: {current_date.date()} | Pred: {pred_return:.4f}")

        # --- SMART SIGNAL LOGIC (Phase 3.5) ---
        # We use Technical Filters to confirm the AI's signal.
        
        # Extract T-1 Technicals
        rsi_val = float(input_data['rsi'].iloc[0]) if 'rsi' in input_data else 50
        # Check momentum if available (using ret_1d or momentum_7)
        momentum_val = float(input_data['momentum_7'].iloc[0]) if 'momentum_7' in input_data else 0
        
        position = "HOLD"
        
        
        # BUY LOGIC:
        # Relaxed: Pred > 0.1%, RSI < 70, Momentum > -0.01
        # OPTIMIZATION: Lowered threshold to 0.001 to activate trades based on observed model output (~0.0015)
        if pred_return > 0.001:
             if rsi_val < 70 and momentum_val > -0.01:
                position = "BUY"
             else:
                pass # print(f"   Skipped BUY: RSI={rsi_val:.1f}, Mom={momentum_val:.3f}")

        # SELL LOGIC:
        # Relaxed: Pred < -0.1%, RSI > 30
        elif pred_return < -0.001:
             if rsi_val > 30:
                 position = "SELL"
             else:
                 pass # print(f"   Skipped SELL: RSI={rsi_val:.1f}")
        
        is_correct = False
        if position == "BUY" and actual_return > 0: is_correct = True
        elif position == "SELL" and actual_return < 0: is_correct = True
        elif position == "HOLD": is_correct = None # ROI is 0
        
        self.results.append({
            "date": current_date,
            "ticker": self.ticker,
            "actual_close": actual_close,
            "pred_close": pred_price,
            "actual_return": actual_return,
            "pred_return": pred_return,
            "signal": position,
            "correct": is_correct
        })


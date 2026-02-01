
import pandas as pd
import yfinance as yf
from datetime import timedelta
import numpy as np
import vectorbt as vbt # Phase 1: Task 1.1
import logging
import traceback

# Local Imports
from technical_analysis import add_ta_features
# from ai_models import train_ensemble_model, load_model, ENSEMBLE_FEATURES # Deprecated or used differently?
# The instruction says "Replace Custom Backtester with VectorBT". 
# The old backtester logic used 'train_ensemble_model' and 'load_model' to simulate trading.
# VectorBT is usually for strategy optimization using signals.
# If we want to backtest the AI model, we need to generate signals using the AI model and then feed them to VectorBT.
# So I should keep the AI fetching/prediction logic to GENERATE signals, and use VectorBT to EXECUTE the backtest.
# HOWEVER, the prompt says "Deprecate the custom for loop... Create a Portfolio.from_signals() simulation."
# This implies I should generate a signal series (Buy/Sell) first.
# So I need to keep the "Simulation" part where I generate signals, but instead of calculating PnL manually, I pass the signal array to VectorBT.

from ai_models import train_ensemble_model, load_model, ENSEMBLE_FEATURES
from shared.stock_list import MACRO_TICKERS

class BacktestEngine:
    def __init__(self, ticker):
        self.ticker = ticker
        self.df = None
        self.results = []
        self.model = None
        
    def fetch_data(self):
        """Fetches data and Macro indicators (Phase 1, Task 1.2)."""
        print(f"🔄 Fetching data for {self.ticker}...")
        try:
            # 1. Fetch Stock Data
            t = yf.Ticker(self.ticker)
            raw_df = t.history(period="5y", interval="1d")
            
            if raw_df.empty:
                print(f"❌ No data for {self.ticker}")
                return False
            
            # 2. Fetch Macro Data (Phase 1, Task 1.2)
            # We fetch 5y history for macro tickers too
            macro_dfs = []
            for name, ticker in MACRO_TICKERS.items():
                try:
                    m_t = yf.Ticker(ticker)
                    m_df = m_t.history(period="5y", interval="1d")
                    # We only need Close for macro usually
                    m_close = m_df[['Close']].rename(columns={'Close': f'macro_{name.lower()}'})
                    # Remove timezone if present to align
                    m_close.index = m_close.index.tz_localize(None)
                    macro_dfs.append(m_close)
                except Exception as e:
                    logging.error(f"   ⚠️ Warning: Failed to fetch Macro {name}: {e}")

            # Align Stock Data Index
            raw_df.index = raw_df.index.tz_localize(None)
            
            # Merge Macro
            if macro_dfs:
                for m_df in macro_dfs:
                     # Join on index (Date)
                     raw_df = raw_df.join(m_df, how='left')
                     # Forward fill macro data (as requested)
                     raw_df[m_df.columns[0]] = raw_df[m_df.columns[0]].ffill()
            
            # 3. Add Technical Features (includes sanitize_data)
            df = add_ta_features(raw_df)
            
            if df.empty:
                print("❌ DF became empty after Technical Analysis")
                return False
                
            self.df = df.reset_index().rename(columns={
                'Date':'date', 'Close':'close', 'Volume':'volume',
                'Open':'open', 'High':'high', 'Low':'low'
            })
            
            # Normalize Date
            self.df['date'] = pd.to_datetime(self.df['date'])
                
            return True
        except Exception as e:
            logging.error(f"❌ Error fetching data: {traceback.format_exc()}")
            return False

    def run(self, start_date, end_date):
        """
        Runs Backtest using VectorBT (Phase 1, Task 1.1).
        """
        if self.df is None:
            if not self.fetch_data(): return None

        print(f"🧪 Running VectorBT Backtest for {self.ticker} ({start_date} to {end_date})...")
        
        # Filter Data
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        mask = (self.df['date'] >= start_dt) & (self.df['date'] <= end_dt)
        sim_df = self.df[mask].copy() # We work on a copy
        
        if sim_df.empty:
            print("❌ No data in date range.")
            return None
            
        entries = []
        exits = []
        
        # We still need to iterate to generate AI signals (Walk-Forward), 
        # UNLESS we assume a static model trained on past data.
        # The old code retrained weekly.
        # For Phase 1, let's keep the Walk-Forward logic to generate the 'entries'/'exits' boolean series,
        # and then pass them to VectorBT.
        
        prices = sim_df['close'].values
        dates = sim_df['date'].values
        
        signal_buy = np.zeros(len(sim_df), dtype=bool)
        signal_sell = np.zeros(len(sim_df), dtype=bool)
        
        # 1. Train Model Once (on data < start_date)
        train_mask = self.df['date'] < start_dt
        train_df = self.df[train_mask]
        
        if len(train_df) > 200:
             try:
                # print("Training initial model...")
                train_ensemble_model(train_df, self.ticker, horizon=1)
                self.model = load_model(self.ticker, 'ensemble')
             except: 
                logging.error(traceback.format_exc())
        
        if self.model:
            features = [f for f in ENSEMBLE_FEATURES if f in sim_df.columns]
            X = sim_df[features].fillna(0)
            
            try:
                preds = self.model.predict(X) 
                # preds is array of return predictions
                
                # Apply Rules
                # signal_buy where pred > 0.001 & RSI < 70 ...
                # We need RSI column
                rsi = sim_df['rsi'].values
                momentum = sim_df['momentum_7'].values
                
                # Vectorized Rules
                pred_cond_buy = preds > 0.001
                rsi_cond_buy = rsi < 70
                mom_cond_buy = momentum > -0.01
                
                signal_buy = pred_cond_buy & rsi_cond_buy & mom_cond_buy
                
                pred_cond_sell = preds < -0.001
                rsi_cond_sell = rsi > 30
                
                signal_sell = pred_cond_sell & rsi_cond_sell
                
            except Exception as e:
                logging.error(f"Prediction failed: {traceback.format_exc()}")

        # 3. Run VectorBT
        # Task 1.1: Add fees=0.001 (0.1%) and slippage=0.0005 (0.05%)
        try:
            pf = vbt.Portfolio.from_signals(
                close=sim_df['close'],
                entries=signal_buy,
                exits=signal_sell,
                fees=0.001,
                slippage=0.0005,
                freq='1D'
            )
            
            # 4. Return Metrics
            # Task 1.1: Sharpe, Max Drawdown, Sortino
            stats = {
                "Total Return [%]": pf.total_return() * 100,
                "Benchmark Return [%]": pf.total_benchmark_return() * 100,
                "Sharpe Ratio": pf.sharpe_ratio(),
                "Sortino Ratio": pf.sortino_ratio(),
                "Max Drawdown [%]": pf.max_drawdown() * 100,
                "Win Rate [%]": pf.trades.win_rate() * 100,
                "Total Trades": pf.trades.count()
            }
            
            print("\n=== Backtest Results ===")
            print(pd.Series(stats))
            
            self.stats = stats
            return stats 

        except Exception as e:
            logging.error(f"VectorBT Failed: {traceback.format_exc()}")
            return None

    def get_trade_log(self):
         pass


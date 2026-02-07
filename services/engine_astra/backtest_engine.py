import pandas as pd
import numpy as np
import logging
import traceback
import vectorbt as vbt
from technical_analysis import add_ta_features

class BacktestEngine:
    def __init__(self, ticker):
        self.ticker = ticker
        self.df = None
        self.stats = {}

    def fetch_data(self, interval='1d'):
        """
        Supports Multi-Interval Fetch (Task 1.2 Enhanced)
        """
        import yfinance as yf
        try:
            # 5y for 1d, 60d for <1h (Yahoo limitation)
            period = "5y" if interval in ['1d', '1wk'] else "60d"
            
            t = yf.Ticker(self.ticker)
            raw_df = t.history(period=period, interval=interval)
            
            if raw_df.empty: return False
            
            # Basic sanitization
            raw_df.index = raw_df.index.tz_localize(None)
            
            # We can't use complex macro features easily on intraday without resampling.
            # For now, we skip macro merge for intraday backtest robustness.
            
            # Tech Analysis
            if interval == '1d':
                df = add_ta_features(raw_df)
            else:
                # Lightweight TA for intraday
                df = raw_df.copy()
                df['rsi'] = vbt.RSI.run(df['Close']).rsi
                
            self.df = df.reset_index().rename(columns={
                'Date':'date', 'Datetime':'date', 'Close':'close', 
                'Volume':'volume', 'Open':'open', 'High':'high', 'Low':'low'
            })
            return True
            
        except Exception as e:
            logging.error(f"Backtest Fetch Error: {e}")
            return False

    def transform_heikin_ashi(self, df):
        """
        Converts standard OHLC to Heikin Ashi (Task 1.2 Enhanced)
        """
        ha_close = (df['open'] + df['high'] + df['low'] + df['close']) / 4
        ha_open =  (df['open'].shift(1) + df['close'].shift(1)) / 2
        # Handle first row
        ha_open.iloc[0] = df['open'].iloc[0]
        
        ha_high = df[['high', 'open', 'close']].max(axis=1)
        ha_low = df[['low', 'open', 'close']].min(axis=1)
        
        return pd.DataFrame({
            'date': df['date'],
            'open': ha_open, 'high': ha_high, 'low': ha_low, 'close': ha_close,
            'volume': df['volume']
        })

    def run_monte_carlo(self, returns, n_sims=1000, days=252):
        """
        Monte Carlo Simulation for Risk (Task 1.2 Enhanced)
        """
        mu = returns.mean()
        sigma = returns.std()
        
        sim_returns = np.random.normal(mu, sigma, (days, n_sims))
        # Cumulative Returns
        paths = (1 + sim_returns).cumprod(axis=0)
        
        # Calculate VaR 95%
        final_vals = paths[-1]
        var_95 = np.percentile(final_vals, 5)
        return var_95

    def run(self, start_date=None, end_date=None, interval='1d', chart_type='candle'):
        if self.df is None:
            if not self.fetch_data(interval): return None

        # Apply Heikin Ashi if requested
        sim_df = self.df.copy()
        if chart_type == 'heikin_ashi':
            sim_df = self.transform_heikin_ashi(sim_df)

        # Filter Date
        if start_date:
            sim_df = sim_df[sim_df['date'] >= pd.to_datetime(start_date)]
        if end_date:
            sim_df = sim_df[sim_df['date'] <= pd.to_datetime(end_date)]
            
        if sim_df.empty: return None

        # --- HYBRID STRATEGY LOGIC (Task 1.2) ---
        # 1. MACD + RSI (Trend + Mom)
        # 2. Bollinger + VWAP (Mean Rev) - VWAP requires volume and typical price
        
        close = sim_df['close']
        
        # VBT Indicators
        rsi = vbt.RSI.run(close).rsi
        macd = vbt.MACD.run(close)
        
        # Example Strategy: MACD Crossover + RSI < 70 (Buy) / RSI > 30 (Sell)
        # We vectorise this using VBT
        
        entries = (macd.macd_above(macd.signal)) & (rsi < 70)
        exits = (macd.macd_below(macd.signal)) | (rsi > 80)
        
        # Portfolio
        pf = vbt.Portfolio.from_signals(
            close, entries, exits, 
            fees=0.001, slippage=0.0005, freq=interval
        )
        
        # Monte Carlo Risk check on strategy returns
        strat_returns = pf.stats()['Total Return [%]'] # Just a float
        # We need daily returns series for MC
        daily_rets = pf.returns()
        var_95 = self.run_monte_carlo(daily_rets)

        stats = {
            "Total Return [%]": pf.total_return() * 100,
            "Sharpe Ratio": pf.sharpe_ratio(),
            "Max Drawdown [%]": pf.max_drawdown() * 100,
            "Win Rate [%]": pf.trades.win_rate() * 100,
            "Total Trades": pf.trades.count(),
            "Monte Carlo VaR (95%)": var_95
        }
        
        self.stats = stats
        return stats

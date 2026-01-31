
import pandas as pd
import yfinance as yf
from ta.trend import ADXIndicator, EMAIndicator

def detect_market_regime():
    """
    Detects market regime based on NIFTY 50 (^NSEI)
    Returns: 1 (Bull), -1 (Bear), 0 (Neutral)
    Logic:
      Bull: Price > 200SMA & 50SMA > 200SMA
      Bear: Price < 200SMA & 50SMA < 200SMA
      Sideways: ADX < 20
    """
    try:
        # Fetch NIFTY 50
        ticker = "^NSEI"
        t = yf.Ticker(ticker)
        df = t.history(period="1y", interval="1d")
        
        if df.empty:
            print("MARKET REGIME: No data for Nifty 50")
            return 0
            
        # Indicators
        close = df['Close']
        ema_50 = EMAIndicator(close=close, window=50).ema_indicator()
        ema_200 = EMAIndicator(close=close, window=200).ema_indicator()
        adx = ADXIndicator(high=df['High'], low=df['Low'], close=close, window=14).adx()
        
        last_price = close.iloc[-1]
        last_50 = ema_50.iloc[-1]
        last_200 = ema_200.iloc[-1]
        last_adx = adx.iloc[-1]
        
        # Sideways Check (Strongest Filter)
        if last_adx < 20:
            return 0 # Neutral/Sideways
            
        # Trend Check
        if last_price > last_200 and last_50 > last_200:
            return 1 # Bull
        elif last_price < last_200 and last_50 < last_200:
            return -1 # Bear
            
        return 0 # Neutral otherwise (Choppy)
        
    except Exception as e:
        print(f"MARKET REGIME ERROR: {e}")
        return 0

import pandas as pd
from ta.trend import MACD, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange # NEW

def add_ta_features(df):
    """
    Adds RSI, MACD, EMA, and ATR.
    """
    # 1. Calculate RSI
    df['rsi'] = RSIIndicator(close=df['Close'], window=14).rsi()

    # 2. Calculate MACD
    macd = MACD(close=df['Close'], window_slow=26, window_fast=12, window_sign=9)
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    
    # 3. Calculate EMAs
    df['ema_50'] = EMAIndicator(close=df['Close'], window=50).ema_indicator()
    df['ema_200'] = EMAIndicator(close=df['Close'], window=200).ema_indicator()
    
    # 4. Calculate ATR (For Stop Loss)
    atr_indicator = AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df['atr'] = atr_indicator.average_true_range()
    
    df.fillna(0, inplace=True)
    return df
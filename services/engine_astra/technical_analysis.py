# services/engine_astra/technical_analysis.py
import pandas as pd
from ta.trend import MACD, EMAIndicator
from ta.momentum import RSIIndicator

def add_ta_features(df):
    """
    Takes a clean OHLCV DataFrame and adds TA indicator columns to it.
    
    Parameters:
    - df (pd.DataFrame): DataFrame with 'Close', 'High', 'Low' columns.
    
    Returns:
    - pd.DataFrame: The original DataFrame with new TA columns.
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
    
    # Fill any 'NaN' (Not a Number) values with 0.
    # TA indicators always have NaNs at the beginning (e.g., you can't have
    # a 50-day EMA on the 10th day of data).
    df.fillna(0, inplace=True)
    
    return df
import pandas as pd
import numpy as np
from ta.trend import MACD, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange

def add_ta_features(df):
    """Adds RSI, MACD, EMA, and ATR to the DataFrame."""
    df['rsi'] = RSIIndicator(close=df['Close'], window=14).rsi()
    
    macd = MACD(close=df['Close'], window_slow=26, window_fast=12, window_sign=9)
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    
    df['ema_50'] = EMAIndicator(close=df['Close'], window=50).ema_indicator()
    df['ema_200'] = EMAIndicator(close=df['Close'], window=200).ema_indicator()
    
    atr_indicator = AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df['atr'] = atr_indicator.average_true_range()
    
    df.fillna(0, inplace=True)
    return df

def score_technical(df):
    """
    Calculates a 0-100 Technical Health Score.
    Based on Trend (MAs), Momentum (RSI/MACD), and Volume.
    """
    if df.empty: return 50.0
    
    last = df.iloc[-1]
    score = 0.0
    price = last['Close']
    
    # 1. Trend (Price vs MAs) - 40 Points
    ma_20 = df['Close'].rolling(window=20).mean().iloc[-1]
    ma_50 = last['ema_50']
    ma_200 = last['ema_200']
    
    trend_score = 0
    if price > ma_20: trend_score += 1
    if price > ma_50: trend_score += 1
    if price > ma_200: trend_score += 2 # Strong long term signal
    
    score += (trend_points := trend_score / 4) * 40
    
    # 2. RSI (Momentum) - 30 Points
    rsi = last['rsi']
    if 40 <= rsi <= 70: score += 30 # Healthy trend
    elif rsi < 30: score += 15 # Oversold (Bounce likely but risky)
    elif rsi > 80: score += 5 # Overbought (Correction likely)
    
    # 3. MACD (Momentum) - 20 Points
    if last['macd'] > last['macd_signal']:
        score += 20
        
    # 4. Volume - 10 Points
    vol_ma = df['Volume'].rolling(window=20).mean().iloc[-1]
    if last['Volume'] > vol_ma:
        score += 10
        
    return min(100.0, score)
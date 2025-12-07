import pandas as pd
import numpy as np
from ta.trend import MACD, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange, BollingerBands

def add_ta_features(df):
    """
    Adds 'Mega' Technical Features for Max Power Prediction.
    Includes: RSI, MACD, EMA, ATR, Bollinger Bands, Momentum, Volume Spikes, Lags.
    """
    # Ensure proper sorting
    df = df.sort_index()
    
    # 1. Basic Indicators
    df['rsi'] = RSIIndicator(close=df['Close'], window=14).rsi()
    
    macd = MACD(close=df['Close'], window_slow=26, window_fast=12, window_sign=9)
    df['macd'] = macd.macd()
    df['macd_signal'] = macd.macd_signal()
    df['macd_hist'] = macd.macd_diff()
    
    df['ema_20'] = EMAIndicator(close=df['Close'], window=20).ema_indicator()
    df['ema_50'] = EMAIndicator(close=df['Close'], window=50).ema_indicator()
    df['ema_200'] = EMAIndicator(close=df['Close'], window=200).ema_indicator()
    
    atr_indicator = AverageTrueRange(high=df['High'], low=df['Low'], close=df['Close'], window=14)
    df['atr'] = atr_indicator.average_true_range()
    
    # 2. Bollinger Bands (Volatility)
    bb = BollingerBands(close=df['Close'], window=20, window_dev=2)
    df['bb_u'] = bb.bollinger_hband()
    df['bb_l'] = bb.bollinger_lband()
    df['bb_m'] = bb.bollinger_mavg()
    
    # 3. Volume Features
    df['vol_20'] = df['Volume'].rolling(window=20).mean()
    df['vol_spike'] = (df['Volume'] > 1.7 * df['vol_20']).astype(int)
    
    # 4. Momentum & Returns
    df['ret_1d'] = df['Close'].pct_change()
    df['log_ret'] = np.log1p(df['ret_1d'])
    df['vol_30'] = df['log_ret'].rolling(30).std() # Historical Volatility
    
    df['momentum_7'] = df['Close'] / df['Close'].shift(7) - 1
    
    # 5. Lag Features (The Secret Sauce for ML)
    # Allows the AI to see "What happened 1, 2, 3 days ago?"
    for lag in [1, 2, 3, 5]:
        df[f'close_lag_{lag}'] = df['Close'].shift(lag)
        
    df.fillna(0, inplace=True)
    return df

def score_technical(df):
    """
    Calculates a 0-100 Technical Health Score.
    """
    if df.empty: return 50.0
    
    last = df.iloc[-1]
    score = 0.0
    price = last['Close']
    
    # Trend (40pts)
    if price > last['ema_20']: score += 10
    if price > last['ema_50']: score += 10
    if price > last['ema_200']: score += 20
    
    # Momentum (30pts)
    rsi = last['rsi']
    if 40 <= rsi <= 70: score += 15
    elif rsi < 30: score += 15 # Oversold bounce potential
    
    if last['macd'] > last['macd_signal']: score += 15
        
    # Volatility/Volume (30pts)
    if price > last['bb_m']: score += 10
    if last['Volume'] > last['vol_20']: score += 10
    if last['vol_spike']: score += 10
        
    return min(100.0, score)
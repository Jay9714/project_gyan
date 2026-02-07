import pandas as pd
import numpy as np
import logging
from ta.trend import EMAIndicator, ADXIndicator, MACD
from ta.volatility import BollingerBands, AverageTrueRange
from ta.momentum import RSIIndicator

class StrategyRegistry:
    def __init__(self):
        # Maps Regime String to Strategy Function
        self.strategies = {
            "BULL_TREND": self.strategy_trend_following,
            "BEAR_TREND": self.strategy_short_scalp,
            "LOW_VOL_SIDEWAYS": self.strategy_mean_reversion,
            "HIGH_VOL_CRASH": self.strategy_volatility_breakout,
            "VOLATILE_COMMODITY": self.strategy_scalping_commodities,
            "EVENT_DRIVEN": self.strategy_event_arb,
            "NEUTRAL": self.strategy_mean_reversion
        }

    def get_strategy(self, regime_name):
        """
        Maps Regime String (BULL_TREND, etc.) to Strategy Function.
        """
        return self.strategies.get(regime_name, self.strategy_mean_reversion)

    # --- CORE ALGOS (Task 2.2 Enhanced) ---

    def strategy_trend_following(self, df):
        """
        Hybrid: EMA Cross + SuperTrend (Simplified via ATR)
        """
        if df.empty: return "HOLD"
        last = df.iloc[-1]
        
        # SuperTrend Logic Proxy: Close > EMA50 + ATR cushion
        st_lower = last['ema_50'] - (last['atr'] * 2) 
        
        if last['close'] > last['ema_20'] and last['rsi'] > 50:
             return "BUY"
        elif last['close'] < last['ema_20']:
             return "SELL"
        return "HOLD"

    def strategy_mean_reversion(self, df):
        """
        Bollinger Bands + RSI Divergence
        """
        if df.empty: return "HOLD"
        last = df.iloc[-1]
        
        bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        lower = bb.bollinger_lband().iloc[-1]
        upper = bb.bollinger_hband().iloc[-1]
        
        if last['close'] < lower and last['rsi'] < 30:
            return "BUY"
        elif last['close'] > upper and last['rsi'] > 70:
            return "SELL"
        return "HOLD"

    def strategy_volatility_breakout(self, df):
        """
        High Volatility Strategy: Breakout of range.
        If price moves > 1 ATR from open.
        """
        if df.empty: return "HOLD"
        last = df.iloc[-1]
        
        range_move = abs(last['close'] - last['open'])
        if range_move > last['atr']:
            if last['close'] > last['open']: return "BUY"
            else: return "SELL"
        return "HOLD"
        
    def strategy_short_scalp(self, df):
        """
        Bear Market Scalping: Sell Rallies.
        """
        if df.empty: return "HOLD"
        last = df.iloc[-1]
        
        if last['rsi'] > 60: return "SELL"
        elif last['rsi'] < 30: return "BUY" # Cover
        return "HOLD"

    def strategy_scalping_commodities(self, df):
        """
        Fast Scalp for MCX/Gold based on Heikin Ashi trends (simulated).
        """
        # Logic same as Trend for now, but tighter SL logic usually exists in OMS
        return self.strategy_trend_following(df)

    def strategy_event_arb(self, df):
        """
        Event Driven: Sentiment plays.
        Takes cues from 'ai_catalyst' (assumed incorporated in verdict elsewhere).
        Here purely technical safety check.
        """
        # If volatile, stand aside unless momentum is huge
        if df.empty: return "HOLD"
        last = df.iloc[-1]
        
        if last['volume'] > (last['vol_20'] * 2): # Volume Spike
             if last['close'] > last['open']: return "BUY"
             return "SELL"
        return "HOLD"
    
    def select_algo_ai(self, context):
        """
        AI Auto-Selection Mock (Task 2.2).
        Context includes: regime, news, capital.
        """
        regime = context.get('regime', 'NEUTRAL')
        return self.get_strategy(regime)

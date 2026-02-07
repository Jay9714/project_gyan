import pandas as pd
import numpy as np
import logging
from ta.trend import ADXIndicator
from ta.volatility import AverageTrueRange

# Try hmmlearn, else fallback
try:
    from hmmlearn.hmm import GaussianHMM
    HAS_HMM = True
except ImportError:
    HAS_HMM = False
    logging.warning("hmmlearn not found. Falling back to rule-based regime detection.")

class MarketRegimeDetector:
    def __init__(self):
        self.model = None
        if HAS_HMM:
            self.model = GaussianHMM(n_components=4, covariance_type="full", n_iter=100)
            
    def prepare_features(self, df):
        """
        Extracts features for Regime Detection:
        1. Returns (Log)
        2. Volatility (ATR %)
        3. Volume Change
        """
        data = df.copy()
        data['log_ret'] = np.log(data['Close'] / data['Close'].shift(1))
        
        atr = AverageTrueRange(high=data['High'], low=data['Low'], close=data['Close'], window=14)
        data['atr_pct'] = atr.average_true_range() / data['Close']
        
        data['vol_change'] = data['Volume'].pct_change()
        
        # Drop NaNs
        data = data.dropna()
        return data

    def train_hmm(self, df):
        if not HAS_HMM: return
        
        feat_df = self.prepare_features(df)
        X = feat_df[['log_ret', 'atr_pct', 'vol_change']].values
        
        # Fit
        self.model.fit(X)
        # We need to map Hidden States 0-3 to human readable regimes (Bull, Bear, etc.)
        # This mapping is tricky unsupervised. We usually sort by Mean Returns.
        
        means = self.model.means_ # Shape (4, 3)
        # Col 0 is log_ret.
        sorted_indices = np.argsort(means[:, 0]) # Sort by returns
        
        self.regime_map = {
            sorted_indices[0]: "HIGH_VOL_CRASH",    # Lowest returns (negative)
            sorted_indices[1]: "BEAR_TREND",        # Negative/Low returns
            sorted_indices[2]: "LOW_VOL_SIDEWAYS",  # Low/Pos returns
            sorted_indices[3]: "BULL_TREND"         # Highest returns
        }
        
    def detect_regime(self, df):
        """
        Returns: Regime String (BULL_TREND, BEAR_TREND, etc.)
        """
        if HAS_HMM and self.model:
            # HMM Logic
            try:
                feat_df = self.prepare_features(df)
                if len(feat_df) < 10: return "NEUTRAL"
                
                X = feat_df[['log_ret', 'atr_pct', 'vol_change']].values
                hidden_states = self.model.predict(X)
                current_state = hidden_states[-1]
                
                return self.regime_map.get(current_state, "NEUTRAL")
            except:
                return self.rule_based_detect(df)
        else:
            return self.rule_based_detect(df)

    def rule_based_detect(self, df):
        """
        Fallback Logic (Task 2.1 Enhanced with ATR)
        """
        if df.empty: return "NEUTRAL"
        
        close = df['Close']
        adx = ADXIndicator(high=df['High'], low=df['Low'], close=close, window=14).adx().iloc[-1]
        
        # ATR Check for Volatility
        atr = AverageTrueRange(high=df['High'], low=df['Low'], close=close, window=14).average_true_range().iloc[-1]
        atr_pct = atr / close.iloc[-1]
        
        sma_200 = close.rolling(200).mean().iloc[-1]
        sma_50 = close.rolling(50).mean().iloc[-1]
        price = close.iloc[-1]
        
        # 1. Crash Check
        if atr_pct > 0.03 and price < sma_200: # >3% daily move & below 200SMA
            return "HIGH_VOL_CRASH"
            
        # 2. Sideways
        if adx < 20: 
            return "LOW_VOL_SIDEWAYS"
            
        # 3. Trends
        if price > sma_200 and sma_50 > sma_200:
            return "BULL_TREND"
        elif price < sma_200:
            return "BEAR_TREND"
            
        return "NEUTRAL"

# Singleton
regime_detector = MarketRegimeDetector()

def detect_market_regime(df=None):
    # If df provided, use it. Else fetch index (handled by caller task usually).
    # For compatibility with old interface, we support df passing.
    if df is not None:
        return regime_detector.detect_regime(df)
        
    # Default fetch Nifty if no DF
    import yfinance as yf
    t = yf.Ticker("^NSEI")
    hist = t.history(period="1y")
    return regime_detector.detect_regime(hist)

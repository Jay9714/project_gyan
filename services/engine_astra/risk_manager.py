import numpy as np

class RiskManager:
    def __init__(self, max_drawdown_pct=0.05, daily_loss_limit=0.02):
        self.max_dd = max_drawdown_pct
        self.daily_limit = daily_loss_limit
        
    def check_entry_allowance(self, current_capital, start_capital, daily_pnl):
        """
        Hard Rule: 
        1. Block if Total DD > 5%
        2. Block if Daily Loss > 2%
        """
        # 1. Total Drawdown
        dd = (start_capital - current_capital) / start_capital
        if dd > self.max_dd:
            return False, f"Total Drawdown Breach ({dd*100:.1f}% > {self.max_dd*100:.1f}%)"
            
        # 2. Daily Loss
        # daily_pnl is usually negative if loss.
        # If daily_limit is 0.02 (2%), we check if daily_pnl < -(capital * 0.02)
        loss_threshold = -(current_capital * self.daily_limit)
        if daily_pnl < loss_threshold:
            return False, f"Daily Loss Limit Hit ({daily_pnl} < {loss_threshold})"
            
        return True, "OK"

    def calculate_position_size(self, capital, price, sl, risk_per_trade=0.01):
        """
        Risk 1% of capital per trade.
        Qty = (Capital * 0.01) / (Entry - SL)
        """
        risk_amt = capital * risk_per_trade
        risk_per_share = abs(price - sl)
        
        if risk_per_share == 0: return 0
        
        qty = int(risk_amt / risk_per_share)
        return max(1, qty)

    def update_trailing_stop(self, entry_price, current_price, current_sl, atr, regime="NEUTRAL"):
        """
        Dynamic Trailing Logic (Task 3.2).
        Tighter trail in High Volatility.
        """
        # Multiplier based on regime
        mult = 2.0
        if regime == "HIGH_VOL_CRASH" or regime == "VOLATILE_COMMODITY":
            mult = 1.0 # Tight trail
        elif regime == "BULL_TREND":
            mult = 3.0 # Loose trail to ride trend
            
        new_sl = current_price - (atr * mult)
        
        # Only move SL UP (for Longs). Logic for Shorts would be opposite.
        # Assuming Long for this function signature simplicity, or handling both:
        
        # Heuristic: If price is above entry, we want to protect profit.
        if new_sl > current_sl:
            return new_sl
            
        return current_sl

risk_manager = RiskManager()

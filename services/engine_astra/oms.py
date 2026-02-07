import datetime
import uuid
import redis
import json
import logging
import os
from shared.costs import calculate_transaction_costs
from services.engine_astra.risk_manager import risk_manager # Task 3.4 Integration

class OrderManagementSystem:
    def __init__(self):
        # Redis Connection
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        self.r = redis.from_url(redis_url, decode_responses=True)
        
        # Initialize Default State if not present
        if not self.r.exists("bot:capital"):
            self.r.set("bot:capital", 10000.0)
        if not self.r.exists("bot:active"):
            self.r.set("bot:active", "false") # Redis stores strings
        if not self.r.exists("bot:trades"):
            self.r.set("bot:trades", json.dumps([]))
            
    def start_bot(self):
        self.r.set("bot:active", "true")
        return "Bot Started"
    
    def stop_bot(self):
        self.r.set("bot:active", "false")
        return "Bot Stopped"
        
    def get_status(self):
        is_active = self.r.get("bot:active") == "true"
        capital = float(self.r.get("bot:capital") or 0.0)
        trades = self.get_trades()
        
        # Calculate PnL (Realized)
        daily_pnl = sum([t.get('pnl', 0) for t in trades if t['status'] == 'CLOSED'])
        
        return {
            "active": is_active,
            "capital": capital,
            "open_positions": len([t for t in trades if t['status'] == 'OPEN']),
            "daily_pnl": daily_pnl,
            "trades_count": len(trades)
        }

    def get_trades(self):
        try:
            trades_json = self.r.get("bot:trades")
            if trades_json:
                return json.loads(trades_json)
            return []
        except:
            return []

    def save_trades(self, trades):
        self.r.set("bot:trades", json.dumps(trades))

    def place_order(self, ticker, direction, price, sl=0.0, tp=0.0, instrument_type="EQUITY_INTRADAY", algo="MANUAL"):
        """
        Task 3.2 Enhanced: Uses Risk Manager & Cost Engine.
        """
        if self.r.get("bot:active") != "true":
            return {"status": "failed", "reason": "Bot is inactive"}

        capital = float(self.r.get("bot:capital") or 0)
        
        # 1. Costs Check
        # Estimate quantity to calculate cost? Or calculate per unit cost.
        # Let's get allowed quantity first.
        
        # 2. Risk Manager Check (Task 3.4)
        status_info = self.get_status()
        daily_pnl = status_info['daily_pnl']
        start_cap = 10000.0 # Ideally tracked separately as 'opening_balance'
        
        is_allowed, reason = risk_manager.check_entry_allowance(capital, start_cap, daily_pnl)
        if not is_allowed:
             return {"status": "failed", "reason": f"Risk Block: {reason}"}
        
        # 3. Position Sizing
        quantity = risk_manager.calculate_position_size(capital, price, sl)
        if quantity < 1: 
             return {"status": "failed", "reason": "Calculated Quantity is 0 (Risk too high or Capital too low)"}

        # 4. Total Cost Check
        est_cost = calculate_transaction_costs(price, quantity, direction, instrument_type)
        margin_needed = (price * quantity) if "INTRADAY" not in instrument_type else (price * quantity * 0.2)
        
        if (margin_needed + est_cost) > capital:
             # Try reducing quantity
             return {"status": "failed", "reason": f"Insufficient Fund. Need {margin_needed+est_cost:.2f}, Have {capital:.2f}"}

        trade = {
            "id": str(uuid.uuid4()),
            "ticker": ticker,
            "direction": direction,
            "entry_price": price,
            "quantity": quantity,
            "sl": sl,
            "tp": tp,
            "status": "OPEN",
            "entry_time": datetime.datetime.now().isoformat(),
            "algo": algo,
            "instrument": instrument_type,
            "est_cost": est_cost
        }
        
        trades = self.get_trades()
        trades.insert(0, trade) # Prepend
        self.save_trades(trades)
        
        logging.info(f"OMS: Placed Trade {trade['id']} | {ticker} {direction} {quantity} @ {price}")
        
        return {"status": "success", "trade": trade}
        
    def close_trade(self, trade_id, exit_price):
        trades = self.get_trades()
        found = False
        for t in trades:
            if t['id'] == trade_id and t['status'] == 'OPEN':
                t['status'] = 'CLOSED'
                t['exit_price'] = exit_price
                t['exit_time'] = datetime.datetime.now().isoformat()
                
                # Calc PnL
                raw_pnl = (exit_price - t['entry_price']) * t['quantity']
                if t['direction'] == 'SELL':
                    raw_pnl = -raw_pnl
                
                # Deduct Costs (Entry + Exit)
                entry_cost = t.get('est_cost', 0)
                exit_cost = calculate_transaction_costs(exit_price, t['quantity'], 
                                                        "SELL" if t['direction']=="BUY" else "BUY", 
                                                        t.get('instrument', 'EQUITY_INTRADAY'))
                
                net_pnl = raw_pnl - entry_cost - exit_cost
                
                t['pnl'] = round(net_pnl, 2)
                
                # Update Capital
                cap = float(self.r.get("bot:capital") or 0)
                self.r.set("bot:capital", cap + net_pnl)
                
                found = True
                break
        
        if found:
            self.save_trades(trades)
            return True
        return False
        
    def check_trailing_stops(self, current_prices):
        """
        Task 3.2: Trailing Logic Hook.
        current_prices: dict {ticker: {'price': 100, 'atr': 5, 'regime': 'BULL'}}
        """
        trades = self.get_trades()
        updated = False
        
        for t in trades:
            if t['status'] == 'OPEN':
                tic = t['ticker']
                if tic in current_prices:
                    curr = current_prices[tic]
                    price = curr['price']
                    current_sl = t.get('sl', 0)
                    
                    if t['direction'] == 'BUY':
                        # Call Risk Manager
                        new_sl = risk_manager.update_trailing_stop(t['entry_price'], price, current_sl, curr.get('atr', 0), curr.get('regime', 'NEUTRAL'))
                        if new_sl > current_sl:
                            t['sl'] = round(new_sl, 2)
                            updated = True
                            logging.info(f"OMS: Trailed SL for {tic} to {new_sl}")
                            
        if updated:
            self.save_trades(trades)

# Standalone instance handling
if __name__ == "__main__":
    oms = OrderManagementSystem()
    print("OMS Initialized in Redis")

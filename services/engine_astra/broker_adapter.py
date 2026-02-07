from abc import ABC, abstractmethod
import logging
import uuid
from datetime import datetime
import redis
import json

class BrokerAdapter(ABC):
    @abstractmethod
    def place_order(self, ticker, quantity, side, order_type="MARKET", price=0.0): pass
    
    @abstractmethod
    def get_positions(self): pass
    
    @abstractmethod
    def cancel_all_orders(self): pass
    
    @abstractmethod
    def get_balance(self): pass

class PaperBroker(BrokerAdapter):
    """
    Shadow Mode Broker.
    Interacts with Redis to simulate trades without real money.
    Matches Phase 4 Task 4.2.
    """
    def __init__(self, redis_url='redis://localhost:6379/0'):
        try:
             self.r = redis.from_url(redis_url, decode_responses=True)
        except:
             self.r = None
             logging.warning("PaperBroker: Redis not available. State will be transient.")
        
        # Initialize Virtual Balance if new
        if self.r and not self.r.exists("paper:balance"):
            self.r.set("paper:balance", 10000.0) # 10 Lakh Virtual Cash

    def place_order(self, ticker, quantity, side, order_type="MARKET", price=0.0):
        """
        Simulates order placement. 
        In strict Shadow Mode, we assume instant fill at current 'price'.
        """
        trade_id = str(uuid.uuid4())
        logging.info(f"PAPER: Placed {side} {quantity} x {ticker} @ {price}")
        
        trade = {
            "id": trade_id,
            "ticker": ticker,
            "side": side,
            "quantity": quantity,
            "price": price,
            "status": "FILLED",
            "timestamp": datetime.now().isoformat()
        }
        
        # Save to Redis List
        if self.r:
            self.r.lpush("paper:trades", json.dumps(trade))
            
            # Update Position Map
            pos_key = f"paper:pos:{ticker}"
            current_qty = int(self.r.get(pos_key) or 0)
            if side == "BUY":
                self.r.set(pos_key, current_qty + quantity)
            elif side == "SELL":
                self.r.set(pos_key, current_qty - quantity)
                
        return {"status": "success", "order_id": trade_id, "fill_price": price}

    def get_positions(self):
        if not self.r: return {}
        # Scan keys
        keys = self.r.keys("paper:pos:*")
        positions = {}
        for k in keys:
            ticker = k.split(":")[-1]
            qty = int(self.r.get(k) or 0)
            if qty != 0:
                positions[ticker] = qty
        return positions

    def cancel_all_orders(self):
        return True # Instant fills -> no open orders

    def get_balance(self):
        if self.r:
            return float(self.r.get("paper:balance") or 0.0)
        return 0.0

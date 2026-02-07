import time
import redis
import json
import random
import os
import signal
import sys

# Configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
TICKERS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "HDFCBANK.NS", "NIFTY_50"]

# Task 4.1: Shoonya/AngelOne WebSocket Simulator
# Real API requires credentials, so we SIMULATE the interface.
# Logic: Generate random ticks close to a "base price" and push to Redis.

def run_live_feed():
    print(f"📡 Connecting to Live Data Stream (Simulated via Redis at {REDIS_URL})...")
    
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
    except Exception as e:
        print(f"❌ Redis Connection Failed: {e}")
        return

    # Base Prices (Mock)
    prices = {
        "RELIANCE.NS": 2500.0,
        "TCS.NS": 3500.0,
        "INFY.NS": 1400.0,
        "HDFCBANK.NS": 1600.0,
        "NIFTY_50": 22000.0
    }

    print("🟢 Live Feed Active. Pushing ticks...")
    
    running = True
    def signal_handler(sig, frame):
        print("\n🛑 Stopping Feed.")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)

    while running:
        for ticker in TICKERS:
            # Simulate movement
            base = prices[ticker]
            change = random.uniform(-base*0.001, base*0.001) # +/- 0.1% volatility per tick
            new_price = base + change
            prices[ticker] = new_price
            
            tick = {
                "ticker": ticker,
                "price": round(new_price, 2),
                "volume": random.randint(1, 100),
                "timestamp": time.time()
            }
            
            # Publish to Redis Channel
            # Channel: 'live_ticks'
            r.publish("live_ticks", json.dumps(tick))
            
            # Also set latest Key for snapshot access
            r.set(f"tick:{ticker}", json.dumps(tick))
            
        time.sleep(1) # 1 Tick per second per stock

if __name__ == "__main__":
    run_live_feed()

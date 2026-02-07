import redis
import time
import pandas as pd
import json
import os
import yfinance as yf

# Task 1.3: Market Replay Service
# Streams historical data into Redis to simulate a live environment (Ghost Mode).

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')

class MarketReplay:
    def __init__(self, ticker, start_date, end_date):
        self.ticker = ticker
        self.start = start_date
        self.end = end_date
        self.r = redis.from_url(REDIS_URL, decode_responses=True)
        
    def fetch_history(self):
        print(f"REPLAY: Fetching history for {self.ticker}...")
        try:
            df = yf.Ticker(self.ticker).history(start=self.start, end=self.end, interval="5m")
            return df
        except:
            return pd.DataFrame()

    def start_stream(self, speed_multiplier=1.0):
        """
        Stream 5m candles as if they are live ticks.
        """
        df = self.fetch_history()
        if df.empty:
            print("REPLAY: No data found.")
            return

        print(f"REPLAY: Starting Stream ({len(df)} candles). Speed={speed_multiplier}x")
        
        for index, row in df.iterrows():
            tick = {
                "ticker": self.ticker,
                "price": row['Close'],
                "volume": row['Volume'],
                "timestamp": index.timestamp(),
                "is_replay": True
            }
            
            # Publish
            self.r.publish("live_ticks", json.dumps(tick))
            self.r.set(f"tick:{self.ticker}", json.dumps(tick))
            
            print(f"   -> Pushed {self.ticker} @ {row['Close']}")
            
            # Wait (Simulation)
            # In real replay, we might wait 5 mins / speed. 
            # For demo, we wait 0.5s
            time.sleep(0.5)

if __name__ == "__main__":
    # Example Usage
    replay = MarketReplay("RELIANCE.NS", "2024-01-01", "2024-01-05")
    replay.start_stream()

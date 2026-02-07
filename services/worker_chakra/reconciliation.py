import time
import redis
import json
import os
import logging
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Local Imports assuming pythonpath set
try:
    from shared.database import StockData, DATABASE_URL
    from services.engine_astra.broker_adapter import PaperBroker
except ImportError:
    # If running standalone, might fail without path setup. 
    # Assumes run via `python -m services.worker_chakra.reconciliation`
    pass

def run_reconciliation():
    """
    Task 5.1: The Reconciliation Worker.
    Compares DB Trade State vs Broker (Paper) State.
    """
    print("🕵️ Starting Reconciliation Worker...")
    
    # 1. Connect to Broker (Shadow)
    broker = PaperBroker()
    broker_positions = broker.get_positions()
    
    print(f"   Broker Positions: {broker_positions}")
    
    # 2. Connect to Internal DB (or Redis OMS State)
    # The 'oms.py' uses Redis 'bot:trades'.
    # Task 3.1 said DB 'trades' table, but OMS implementation used Redis for Demo.
    # We will reconcile against Redis OMS state.
    
    r = redis.from_url(os.environ.get('REDIS_URL', 'redis://localhost:6379/0'), decode_responses=True)
    trades_json = r.get("bot:trades")
    oms_trades = json.loads(trades_json) if trades_json else []
    
    # Calculate OMS Net Positions
    oms_positions = {}
    for t in oms_trades:
        if t['status'] == 'OPEN':
            tic = t['ticker']
            qty = t['quantity']
            if t['direction'] == 'SELL': qty = -qty
            oms_positions[tic] = oms_positions.get(tic, 0) + qty
            
    print(f"   OMS Positions:    {oms_positions}")
    
    # 3. Compare
    discrepancies = []
    
    all_tickers = set(broker_positions.keys()) | set(oms_positions.keys())
    
    for ticker in all_tickers:
        b_qty = broker_positions.get(ticker, 0)
        o_qty = oms_positions.get(ticker, 0)
        
        if b_qty != o_qty:
            msg = f"MISMATCH {ticker}: Broker={b_qty}, OMS={o_qty}"
            discrepancies.append(msg)
            print(f"❌ {msg}")
        else:
            print(f"✅ {ticker} Matched")
            
    if discrepancies:
        print("⚠️ ALERTS TRIGGERED!")
        # Send Notification (Simulated)
        # requests.post(TELEGRAM_URL, json={"text": str(discrepancies)})
    else:
        print("✨ System Healthy. Zero Discrepancies.")

if __name__ == "__main__":
    run_reconciliation()

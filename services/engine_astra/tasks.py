import os
import time
import pandas as pd
import yfinance as yf
from celery import Celery
from sqlalchemy.exc import IntegrityError
import numpy as np 

# Import our upgraded DB and new TA module
from database import SessionLocal, create_db_and_tables, StockData, FundamentalData
from stock_list import NIFTY50_TICKERS
from technical_analysis import add_ta_features # <-- Import our new TA functions

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
app = Celery('astra_tasks', broker=REDIS_URL, backend=REDIS_URL)

app.conf.task_default_queue = 'astra_q'

# We have removed the 'setup_on_startup' hook.
# The 'migration' service now handles all database setup.

@app.task(name="astra.run_nightly_update")
def run_nightly_update():
    """
    This is the full Phase 3 data pipeline task.
    """
    print("ASTRA: Received job: run_nightly_update. Starting...")
    db = SessionLocal()
    
    for ticker in NIFTY50_TICKERS:
        print(f"ASTRA: Processing {ticker}...")
        try:
            # 1. Fetch Price Data
            t = yf.Ticker(ticker)
            data = t.history(period="2y", interval="1d", auto_adjust=False)
            
            if data.empty:
                print(f"ASTRA: No price data found for {ticker}. Skipping.")
                continue
            
            # 2. Calculate TA Features
            data_with_ta = add_ta_features(data)
            
            # 3. Save Price + TA Data
            for index, row in data_with_ta.iterrows():
                if pd.isna(row['Open']) or pd.isna(row['Close']):
                    continue 
                        
                db.merge(StockData(
                    ticker=ticker,
                    date=index.date(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']),
                    # --- Add TA data to save ---
                    rsi=float(row['rsi']),
                    macd=float(row['macd']),
                    macd_signal=float(row['macd_signal']),
                    ema_50=float(row['ema_50']),
                    ema_200=float(row['ema_200'])
                ))
            
            # 4. Fetch & Save Fundamental Data
            info = t.info
            if info and info.get('marketCap'):
                db.merge(FundamentalData(
                    ticker=ticker,
                    company_name=info.get('longName'),
                    sector=info.get('sector'),
                    industry=info.get('industry'),
                    market_cap=float(info.get('marketCap')),
                    pe_ratio=float(info.get('trailingPE', 0)),
                    eps=float(info.get('trailingEps', 0)),
                    beta=float(info.get('beta', 0))
                ))
            else:
                print(f"ASTRA: No fundamental data found for {ticker}.")

            db.commit()
            print(f"ASTRA: Successfully saved all data for {ticker}.")

        except IntegrityError as e:
            db.rollback()
            print(f"ASTRA: Skipping duplicate data for {ticker}.")
        except Exception as e:
            db.rollback()
            print(f"ASTRA: ERROR processing {ticker}: {e}")
        
        time.sleep(1) 
            
    db.close()
    print("ASTRA: Nightly update complete.")
    return f"Successfully processed {len(NIFTY50_TICKERS)} tickers."
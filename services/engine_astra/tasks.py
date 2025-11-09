# services/engine_astra/tasks.py
import os
import time
import pandas as pd
import yfinance as yf
from celery import Celery
from sqlalchemy.exc import IntegrityError
import numpy as np # Import numpy

# Import our new database and stock list
from database import SessionLocal, create_db_and_tables, StockData
from stock_list import NIFTY50_TICKERS

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
app = Celery('astra_tasks', broker=REDIS_URL, backend=REDIS_URL)

app.conf.task_default_queue = 'astra_q'

@app.on_after_configure.connect
def setup_on_startup(sender, **kwargs):
    """
    Run this once when the Astra worker first starts.
    This creates our PostgreSQL tables.
    """
    print("Astra: Running startup task: Creating DB tables...")
    create_db_and_tables()

@app.task(name="astra.run_data_pipeline")
def run_data_pipeline():
    """
    This is the main data pipeline task.
    This version flattens the multi-index columns from yfinance.
    """
    print("ASTRA: Received job: run_data_pipeline. Starting...")
    db = SessionLocal()
    
    for ticker in NIFTY50_TICKERS:
        print(f"ASTRA: Fetching data for {ticker}...")
        try:
            # 1. Fetch data. This returns a MultiIndex DataFrame.
            data = yf.download(ticker, period="2y", interval="1d", auto_adjust=False)
            
            if data.empty:
                print(f"ASTRA: No data found for {ticker}. Skipping.")
                continue
            
            # --- THIS IS THE ROBUST FIX ---
            # 2. Flatten the MultiIndex columns.
            # This turns [('Open', 'RELIANCE.NS'), ('Close', 'RELIANCE.NS')]
            # into a simple list: ['Open', 'Close']
            data.columns = data.columns.get_level_values(0)
            # --- END FIX ---

            # 3. Iterate using iterrows().
            # Now 'row' will be a simple Series, and 'row['Open']' will work.
            for index, row in data.iterrows():
                
                # 4. Check for NaN (Not a Number)
                # This check will now work correctly.
                if pd.isna(row['Open']) or pd.isna(row['Close']):
                    continue 
                        
                db.merge(StockData(
                    ticker=ticker,
                    date=index.date(),           # This is the date
                    open=float(row['Open']),     # Cast to simple Python float
                    high=float(row['High']),   # Cast to simple Python float
                    low=float(row['Low']),     # Cast to simple Python float
                    close=float(row['Close']),   # Cast to simple Python float
                    volume=int(row['Volume'])    # Cast to simple Python int
                ))
            
            db.commit()
            print(f"ASTRA: Successfully saved/updated data for {ticker}.")

        except IntegrityError as e:
            db.rollback()
            print(f"ASTRA: Skipping duplicate data for {ticker}.")
        except Exception as e:
            db.rollback()
            print(f"ASTRA: ERROR processing {ticker}: {e}")
        
        time.sleep(1) 
            
    db.close()
    print("ASTRA: Data pipeline complete.")
    return f"Successfully processed {len(NIFTY50_TICKERS)} tickers."
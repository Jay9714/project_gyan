import os
import time
import pandas as pd
import yfinance as yf
from datetime import datetime
from celery import Celery
from sqlalchemy.exc import IntegrityError
import numpy as np 

from database import SessionLocal, create_db_and_tables, StockData, FundamentalData
from stock_list import NIFTY50_TICKERS
from technical_analysis import add_ta_features
from ai_models import train_prophet_model, train_classifier_model
from rules_engine import analyze_stock

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
app = Celery('astra_tasks', broker=REDIS_URL, backend=REDIS_URL)
app.conf.task_default_queue = 'astra_q'

@app.task(name="astra.run_nightly_update")
def run_nightly_update():
    print("ASTRA: Received job: run_nightly_update. Starting Phase 4 Logic...")
    db = SessionLocal()
    
    for ticker in NIFTY50_TICKERS:
        print(f"ASTRA: Processing {ticker}...")
        try:
            # --- 1. FETCH DATA ---
            t = yf.Ticker(ticker)
            data = t.history(period="2y", interval="1d", auto_adjust=False)
            
            if data.empty:
                continue
            
            # --- 2. CALCULATE TA ---
            data_with_ta = add_ta_features(data)
            
            # --- 3. SAVE HISTORY ---
            for index, row in data_with_ta.iterrows():
                if pd.isna(row['Open']) or pd.isna(row['Close']): continue 
                db.merge(StockData(
                    ticker=ticker,
                    date=index.date(),
                    open=float(row['Open']),
                    high=float(row['High']),
                    low=float(row['Low']),
                    close=float(row['Close']),
                    volume=int(row['Volume']),
                    rsi=float(row['rsi']),
                    macd=float(row['macd']),
                    macd_signal=float(row['macd_signal']),
                    ema_50=float(row['ema_50']),
                    ema_200=float(row['ema_200'])
                ))
            
            # --- 4. AI TRAINING & PREDICTION ---
            ai_df = data_with_ta.reset_index().rename(columns={
                'Date': 'date', 'Close': 'close', 'Volume': 'volume',
                'Open': 'open', 'High': 'high', 'Low': 'low'
            })
            
            print(f"ASTRA: Training AI models for {ticker}...")
            prophet_model, forecast = train_prophet_model(ai_df, ticker)
            rf_model, confidence = train_classifier_model(ai_df, ticker)
            
            # --- 5. RULES ENGINE DECISION ---
            latest_row = data_with_ta.iloc[-1]
            analysis_result = analyze_stock(
                ticker, 
                current_price=float(latest_row['Close']),
                rsi=float(latest_row['rsi']),
                macd=float(latest_row['macd']),
                ema_50=float(latest_row['ema_50']),
                ai_confidence=confidence,
                prophet_forecast=forecast
            )
            
            # --- 6. SAVE VERDICT & FUNDAMENTALS ---
            info = t.info
            db.merge(FundamentalData(
                ticker=ticker,
                company_name=info.get('longName', ticker),
                sector=info.get('sector', 'Unknown'),
                industry=info.get('industry', 'Unknown'),
                market_cap=float(info.get('marketCap', 0)),
                pe_ratio=float(info.get('trailingPE', 0)),
                eps=float(info.get('trailingEps', 0)),
                beta=float(info.get('beta', 0)),
                
                # --- THE FIX: Cast numpy types to pure Python floats ---
                ai_verdict=str(analysis_result['verdict']),
                ai_confidence=float(analysis_result['ai_confidence']),
                target_price=float(analysis_result['target_price']),
                ai_reasoning=str(analysis_result['reasoning']),
                last_updated=datetime.now().date()
                # -------------------------------------------------------
            ))

            db.commit()
            print(f"ASTRA: DONE {ticker}. Verdict: {analysis_result['verdict']}")

        except Exception as e:
            db.rollback()
            print(f"ASTRA: ERROR processing {ticker}: {e}")
        
        time.sleep(1) 
            
    db.close()
    print("ASTRA: Nightly update complete.")
    return "Success"
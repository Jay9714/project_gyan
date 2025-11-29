import os
import time
import math
import random
import pandas as pd
import yfinance as yf
from datetime import datetime
from celery import Celery
from sqlalchemy.exc import IntegrityError
from sqlalchemy.dialects.postgresql import insert 
import numpy as np 

from shared.database import SessionLocal, create_db_and_tables, StockData, FundamentalData
from shared.stock_list import NIFTY50_TICKERS
from technical_analysis import add_ta_features
from ai_models import train_prophet_model, train_classifier_model
from rules_engine import analyze_stock
from fundamental_analysis import compute_fundamental_ratios, score_fundamentals, calculate_piotroski_f_score, altman_z_score, get_fundamental_score, get_risk_score
from shared.news_analysis import analyze_news_sentiment


REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
app = Celery('astra_tasks', broker=REDIS_URL, backend=REDIS_URL)
app.conf.task_default_queue = 'astra_q'

def process_one_stock(ticker, db):
    print(f"ASTRA: Processing {ticker}...")
    try:
        t = yf.Ticker(ticker)
        
        # --- 1. FETCH PRICE ---
        data = t.history(period="2y", interval="1d", auto_adjust=False)
        if data.empty:
            print(f"ASTRA: No data found for {ticker}.")
            return False
        
        # --- 2. CALCULATE TA ---
        data_with_ta = add_ta_features(data)
        
        # --- 3. SAVE HISTORY ---
        stock_records = []
        for index, row in data_with_ta.iterrows():
            if pd.isna(row['Open']): continue
            stock_records.append({
                "ticker": ticker, "date": index.date(),
                "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close']),
                "volume": int(row['Volume']), "rsi": float(row['rsi']), "macd": float(row['macd']), "macd_signal": float(row['macd_signal']),
                "ema_50": float(row['ema_50']), "ema_200": float(row['ema_200']), "atr": float(row.get('atr', 0.0))
            })
        
        if stock_records:
            stmt = insert(StockData).values(stock_records)
            update_dict = {
                 "open": stmt.excluded.open, "high": stmt.excluded.high, "low": stmt.excluded.low,
                 "close": stmt.excluded.close, "volume": stmt.excluded.volume, "rsi": stmt.excluded.rsi,
                 "macd": stmt.excluded.macd, "macd_signal": stmt.excluded.macd_signal,
                 "ema_50": stmt.excluded.ema_50, "ema_200": stmt.excluded.ema_200, "atr": stmt.excluded.atr
            }
            stmt = stmt.on_conflict_do_update(index_elements=['ticker', 'date'], set_=update_dict)
            db.execute(stmt)

        # --- 4. FUNDAMENTALS & RISK ---
        fin = t.financials
        bal = t.balance_sheet
        cf = t.cashflow
        info = t.info
        
        f_score = calculate_piotroski_f_score(t)
        z_score = altman_z_score(fin, bal, info.get('marketCap', 0))
        funda_dict = compute_fundamental_ratios(t)
        
        ratios_for_score = {'roe': funda_dict['roe'], 'debt_to_equity': funda_dict['debt_to_equity'], 'revenue_growth': funda_dict['revenue_growth']}
        risk_for_score = {'f_score': f_score, 'z_score': z_score}
        
        score_fund = get_fundamental_score(ratios_for_score, risk_for_score)
        score_risk = get_risk_score(ratios_for_score, risk_for_score)
        
        # --- NEW: Calculate News Sentiment ---
        score_news = analyze_news_sentiment(ticker)
        print(f"ASTRA: News Sentiment for {ticker}: {score_news}")
        # -------------------------------------
        
        # --- 5. AI & VERDICT ---
        ai_df = data_with_ta.reset_index().rename(columns={'Date':'date','Close':'close','Volume':'volume','Open':'open','High':'high','Low':'low'})
        prophet_model, forecast = train_prophet_model(ai_df, ticker)
        rf_model, confidence = train_classifier_model(ai_df, ticker)
        
        latest = data_with_ta.iloc[-1]
        atr_val = latest.get('atr', latest['Close']*0.02)

        # --- FIX: Pass sentiment_score to analyze_stock ---
        analysis = analyze_stock(
            ticker, float(latest['Close']), float(latest['rsi']), float(latest['macd']),
            float(latest['ema_50']), float(atr_val),
            float(confidence), forecast, funda_dict, 
            float(score_news) # <--- THIS WAS MISSING
        )
        # --------------------------------------------------

        # --- 6. SAVE EVERYTHING ---
        existing = db.query(FundamentalData).filter(FundamentalData.ticker == ticker).first()
        data_dict = {
            "company_name": info.get('longName', ticker),
            "sector": info.get('sector', 'Unknown'), "industry": info.get('industry', 'Unknown'),
            "market_cap": float(info.get('marketCap', 0)), "pe_ratio": float(info.get('trailingPE', 0)),
            "eps": float(info.get('trailingEps', 0)), "beta": float(info.get('beta', 0)),
            
            "roe": float(funda_dict['roe']), "debt_to_equity": float(funda_dict['debt_to_equity']),
            "free_cash_flow": float(funda_dict['free_cash_flow']), "revenue_growth": float(funda_dict['revenue_growth']),
            
            "piotroski_f_score": int(f_score), "altman_z_score": float(z_score),
            "score_fundamental": float(score_fund), "score_risk": float(score_risk), 
            "news_sentiment": float(score_news), # Save to DB
            
            "st_verdict": analysis['st']['verdict'], "st_target": float(analysis['st']['target']), "st_stoploss": float(analysis['st']['sl']),
            "mt_verdict": analysis['mt']['verdict'], "mt_target": float(analysis['mt']['target']), "mt_stoploss": float(analysis['mt']['sl']),
            "lt_verdict": analysis['lt']['verdict'], "lt_target": float(analysis['lt']['target']), "lt_stoploss": float(analysis['lt']['sl']),
            "ai_reasoning": analysis['reasoning'], "ai_confidence": float(analysis['ai_confidence']), 
            "last_updated": datetime.now().date()
        }
        
        if existing:
            for k, v in data_dict.items(): setattr(existing, k, v)
        else:
            db.add(FundamentalData(ticker=ticker, **data_dict))
            
        db.commit()
        print(f"ASTRA: DONE {ticker}. Verdict: {analysis['st']['verdict']}")
        return True

    except Exception as e:
        db.rollback()
        print(f"ASTRA: ERROR {ticker}: {e}")
        if "429" in str(e):
            time.sleep(60)
        return False

@app.task(name="astra.run_nightly_update")
def run_nightly_update():
    print("ASTRA: Starting Nightly Update...")
    db = SessionLocal()
    for ticker in NIFTY50_TICKERS:
        process_one_stock(ticker, db)
        delay = random.uniform(2.0, 5.0)
        print(f"ASTRA: Sleeping {delay:.2f}s...")
        time.sleep(delay)
    db.close()
    print("ASTRA: Nightly update complete.")
    return "Success"

@app.task(name="astra.run_single_stock_update")
def run_single_stock_update(ticker):
    print(f"ASTRA: Received on-demand request for {ticker}...")
    db = SessionLocal()
    success = process_one_stock(ticker, db)
    db.close()
    return f"Processed {ticker}: {success}"

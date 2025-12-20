import os
import time
import math
import random
import pandas as pd
import yfinance as yf
from datetime import datetime
from celery import Celery
from sqlalchemy.dialects.postgresql import insert 
import numpy as np 

from shared.database import SessionLocal, create_db_and_tables, StockData, FundamentalData, SectorPerformance
from shared.stock_list import NIFTY50_TICKERS
from technical_analysis import add_ta_features
from ai_models import train_prophet_model, train_classifier_model, train_ensemble_model
from rules_engine import analyze_stock

from shared.fundamental_analysis import compute_fundamental_ratios, calculate_piotroski_f_score, altman_z_score, beneish_m_score, get_fundamental_score, get_risk_score
from shared.news_analysis import analyze_news_sentiment
from shared.sector_analysis import update_sector_trends
from chanakya_agent import generate_chanakya_reasoning # NEW IMPORT

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
app = Celery('astra_tasks', broker=REDIS_URL, backend=REDIS_URL)
app.conf.task_default_queue = 'astra_q'


def fetch_ticker_data_with_retry(ticker, retries=3):
    """Robust fetcher to handle Yahoo Finance network errors."""
    for i in range(retries):
        try:
            t = yf.Ticker(ticker)
            _ = t.info 
            return t
        except Exception as e:
            if i == retries - 1:
                print(f"ASTRA: Failed to fetch {ticker} after {retries} attempts: {e}")
                return None
            time.sleep(2) # Wait 2s before retry
    return None


def get_sector_status(db, sector_name):
    """
    Finds the sector status from DB using fuzzy matching.
    """
    if not sector_name or sector_name == "Unknown": return "NEUTRAL"
    
    # Try direct match first
    sec = db.query(SectorPerformance).filter(SectorPerformance.sector_name == sector_name).first()
    if sec: return sec.status
    
    # Try partial match (e.g., 'Financial Services' -> 'Financial')
    all_sectors = db.query(SectorPerformance).all()
    for s in all_sectors:
        if s.sector_name.lower() in sector_name.lower() or sector_name.lower() in s.sector_name.lower():
            return s.status
            
    return "NEUTRAL"


def process_one_stock(ticker, db):
    print(f"ASTRA: Processing {ticker}...")
    try:
        t = fetch_ticker_data_with_retry(ticker)
        if not t: return False
        
        # 2. PRICE DATA
        data = t.history(period="2y", interval="1d", auto_adjust=False)
        if data.empty: return False
        data_with_ta = add_ta_features(data)
        
        # Save History
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
            update_dict = { k: stmt.excluded[k] for k in ['open','high','low','close','volume','rsi','macd','macd_signal','ema_50','ema_200','atr']}
            stmt = stmt.on_conflict_do_update(index_elements=['ticker', 'date'], set_=update_dict)
            db.execute(stmt)

        # 3. FUNDAMENTALS
        fin = t.financials; bal = t.balance_sheet; cf = t.cashflow; info = t.info
        f_score = calculate_piotroski_f_score(t)
        z_score = altman_z_score(fin, bal, info.get('marketCap', 0))
        m_score = beneish_m_score(fin, bal, cf)
        funda_dict = compute_fundamental_ratios(t)
        
        # Calculate Scores
        comp_score = 0
        if f_score >= 7: comp_score += 30
        elif f_score >= 5: comp_score += 15
        if funda_dict['revenue_growth'] > 0.15: comp_score += 20
        pe = info.get('trailingPE', 0)
        if 0 < pe < 25: comp_score += 20
        latest_rsi = data_with_ta['rsi'].iloc[-1]
        if 40 <= latest_rsi <= 70: comp_score += 30

        funda_dict.update({'piotroski_f_score': f_score, 'altman_z_score': z_score, 'beneish_m_score': m_score})
        score_news = analyze_news_sentiment(ticker)

        # 4. AI & VERDICT
        ai_df = data_with_ta.reset_index().rename(columns={'Date':'date','Close':'close','Volume':'volume','Open':'open','High':'high','Low':'low'})
        prophet_model, forecast = train_prophet_model(ai_df, ticker)
        rf_model, confidence = train_classifier_model(ai_df, ticker)
        
        features = ['open','high','low','close','volume','rsi','macd','atr','ema_50','bb_u','bb_l','momentum_7','vol_spike','close_lag_1','close_lag_2','close_lag_3','close_lag_5']
        stack_model, stack_rmse = train_ensemble_model(ai_df, ticker, horizon=1)
        
        # Predict Return -> Price
        last_row = ai_df.iloc[[-1]][features].fillna(0)
        predicted_return = float(stack_model.predict(last_row)[0]) if stack_model else 0.0
        current_close = float(ai_df['close'].iloc[-1])
        predicted_close = current_close * (1 + predicted_return)

        latest = data_with_ta.iloc[-1]
        atr_val = latest.get('atr', latest['Close']*0.02)
        
        # SECTOR CHECK
        sector_name = info.get('sector', 'Unknown')
        sector_status = get_sector_status(db, sector_name)

        analysis = analyze_stock(
            ticker, float(latest['Close']), float(latest['rsi']), float(latest['macd']),
            float(latest['ema_50']), float(atr_val),
            float(confidence), forecast, 
            funda_dict, float(score_news),
            sector=sector_name,
            sector_status=sector_status 
        )
        
        # --- PHASE 3: AGENTIC REASONING ---
        summary = {
            'sector': sector_name,
            'sector_status': sector_status,
            'trend': 'Bullish' if latest['Close'] > latest['ema_50'] else 'Bearish',
            'quality': 'High' if f_score >= 7 else 'Low',
            'risk': 'High' if z_score < 1.8 else 'Safe',
            'target': analysis['st']['target']
        }
        
        ai_narrative = generate_chanakya_reasoning(
            ticker, 
            analysis['st']['verdict'], 
            analysis['ai_confidence'],
            summary
        )
        
        # Fallback if LLM fails
        if "Chanakya is" in ai_narrative and len(ai_narrative) < 50:
             final_reasoning = analysis['reasoning'] + f"\n\n**Agent Note:** {ai_narrative}"
        else:
             final_reasoning = ai_narrative
        # ----------------------------------

        # 5. SAVE
        existing = db.query(FundamentalData).filter(FundamentalData.ticker == ticker).first()
        data_dict = {
            "company_name": info.get('longName', ticker),
            "sector": sector_name, "industry": info.get('industry', 'Unknown'),
            "market_cap": float(info.get('marketCap', 0)), "pe_ratio": float(info.get('trailingPE', 0)),
            "eps": float(info.get('trailingEps', 0)), "beta": float(info.get('beta', 0)),
            "piotroski_f_score": int(f_score), "altman_z_score": float(z_score), "beneish_m_score": float(m_score),
            "score_fundamental": 50.0, "score_news": float(score_news),
            "st_verdict": analysis['st']['verdict'], "st_target": float(analysis['st']['target']), "st_stoploss": float(analysis['st']['sl']),
            "mt_verdict": analysis['mt']['verdict'], "mt_target": float(analysis['mt']['target']), "mt_stoploss": float(analysis['mt']['sl']),
            "lt_verdict": analysis['lt']['verdict'], "lt_target": float(analysis['lt']['target']), "lt_stoploss": float(analysis['lt']['sl']),
            "ai_reasoning": final_reasoning, # Replaces rule-based text
            "ai_confidence": float(analysis['ai_confidence']), 
            "predicted_close": predicted_close, "ensemble_score": float(comp_score),
            "last_updated": datetime.now().date()
        }
        
        if existing:
            for k, v in data_dict.items(): setattr(existing, k, v)
        else:
            db.add(FundamentalData(ticker=ticker, **data_dict))
            
        db.commit()
        print(f"ASTRA: DONE {ticker}. Sector: {sector_status}")
        return True

    except Exception as e:
        db.rollback()
        print(f"ASTRA: ERROR {ticker}: {e}")
        return False


@app.task(name="astra.run_sector_update")
def run_sector_update():
    db = SessionLocal()
    update_sector_trends(db)
    db.close()
    return "Sector Update Complete"


@app.task(name="astra.run_nightly_update")
def run_nightly_update():
    print("ASTRA: Starting Nightly Update...")
    db = SessionLocal()
    for ticker in NIFTY50_TICKERS:
        process_one_stock(ticker, db)
        time.sleep(random.uniform(2.0, 5.0))
    db.close()
    print("ASTRA: Nightly update complete.")
    return "Success"


@app.task(name="astra.run_single_stock_update")
def run_single_stock_update(ticker):
    print(f"ASTRA: Received on-demand request for {ticker}...")
    
    # 1. Update Sectors FIRST
    db = SessionLocal()
    try:
        update_sector_trends(db)
    except Exception as e:
        print(f"ASTRA: Sector update warning: {e}")
    db.close()
    
    # 2. Analyze the Stock
    db = SessionLocal()
    success = process_one_stock(ticker, db)
    db.close()
    return f"Processed {ticker}: {success}"
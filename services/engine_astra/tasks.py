import os
import time
import math
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

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
app = Celery('astra_tasks', broker=REDIS_URL, backend=REDIS_URL)
app.conf.task_default_queue = 'astra_q'

# --- NEW HELPER: Adapted from automated_stock_analyzer.py ---
def calculate_advanced_fundamentals(stock_obj):
    """
    Computes ROE, Debt-to-Equity, FCF, and Growth using yfinance data.
    Returns a dictionary of ratios.
    """
    ratios = {
        "roe": 0.0,
        "debt_to_equity": 0.0,
        "free_cash_flow": 0.0,
        "revenue_growth": 0.0
    }
    
    try:
        # 1. Fetch Tables
        bs = stock_obj.balance_sheet
        fin = stock_obj.financials
        cf = stock_obj.cashflow
        fast = stock_obj.fast_info
        info = stock_obj.info

        # 2. ROE (Net Income / Total Equity)
        net_income = None
        total_equity = None
        
        # Find Net Income
        if not fin.empty:
            for key in ["Net Income", "Net Income Common Stockholders", "Net Income Applicable To Common Shares"]:
                if key in fin.index:
                    net_income = fin.loc[key].iloc[0]
                    break
        
        # Find Equity
        if not bs.empty:
            for key in ["Total Stockholder Equity", "Total Equity", "Stockholders Equity"]:
                if key in bs.index:
                    total_equity = bs.loc[key].iloc[0]
                    break
                    
        if net_income and total_equity and total_equity != 0:
            ratios["roe"] = float(net_income / total_equity)

        # 3. Debt to Equity
        total_debt = None
        # Try fast_info first (often cleaner)
        if 'totalDebt' in fast: 
            total_debt = fast['totalDebt']
        elif not bs.empty and "Total Debt" in bs.index:
            total_debt = bs.loc["Total Debt"].iloc[0]
            
        if total_debt is not None and total_equity and total_equity != 0:
            ratios["debt_to_equity"] = float(total_debt / total_equity)

        # 4. Free Cash Flow (Operating Cash Flow + CapEx)
        if not cf.empty and "Total Cash From Operating Activities" in cf.index:
            ocf = cf.loc["Total Cash From Operating Activities"].iloc[0]
            capex = 0
            if "Capital Expenditures" in cf.index:
                capex = cf.loc["Capital Expenditures"].iloc[0]
            ratios["free_cash_flow"] = float(ocf + capex)
        elif 'freeCashflow' in info:
             ratios["free_cash_flow"] = float(info['freeCashflow'])

        # 5. Revenue Growth (Current vs Previous year)
        if not fin.empty:
            for key in ["Total Revenue", "Revenue", "Total revenues"]:
                if key in fin.index:
                    rev_series = fin.loc[key]
                    if len(rev_series) >= 2:
                        current_rev = rev_series.iloc[0]
                        prev_rev = rev_series.iloc[1]
                        if prev_rev != 0:
                            ratios["revenue_growth"] = float((current_rev - prev_rev) / prev_rev)
                    break
        elif 'revenueGrowth' in info:
             ratios["revenue_growth"] = float(info['revenueGrowth'])

    except Exception as e:
        print(f"ASTRA: Fundamental Calc Warning: {e}")
    
    return ratios

# --- MAIN LOGIC ---
def process_one_stock(ticker, db):
    print(f"ASTRA: Processing {ticker}...")
    try:
        t = yf.Ticker(ticker)
        
        # --- 1. FETCH PRICE DATA ---
        data = t.history(period="2y", interval="1d", auto_adjust=False)
        if data.empty:
            print(f"ASTRA: No data found for {ticker}.")
            return False
        
        # --- 2. CALCULATE TA ---
        data_with_ta = add_ta_features(data)
        
        # --- 3. SAVE HISTORY (UPSERT) ---
        stock_records = []
        for index, row in data_with_ta.iterrows():
            if pd.isna(row['Open']) or pd.isna(row['Close']): continue
            stock_records.append({
                "ticker": ticker,
                "date": index.date(),
                "open": float(row['Open']), "high": float(row['High']),
                "low": float(row['Low']), "close": float(row['Close']),
                "volume": int(row['Volume']), "rsi": float(row['rsi']),
                "macd": float(row['macd']), "macd_signal": float(row['macd_signal']),
                "ema_50": float(row['ema_50']), "ema_200": float(row['ema_200']),
                "atr": float(row.get('atr', 0.0))
            })
        
        if stock_records:
            stmt = insert(StockData).values(stock_records)
            update_dict = {c: stmt.excluded.getattr(c) for c in [
                "open", "high", "low", "close", "volume", "rsi", "macd", 
                "macd_signal", "ema_50", "ema_200", "atr"
            ]}
            # Fix for getattr issue in newer SQLAlchemy, using direct column access
            update_dict = {
                 "open": stmt.excluded.open, "high": stmt.excluded.high, "low": stmt.excluded.low,
                 "close": stmt.excluded.close, "volume": stmt.excluded.volume, "rsi": stmt.excluded.rsi,
                 "macd": stmt.excluded.macd, "macd_signal": stmt.excluded.macd_signal,
                 "ema_50": stmt.excluded.ema_50, "ema_200": stmt.excluded.ema_200, "atr": stmt.excluded.atr
            }

            stmt = stmt.on_conflict_do_update(index_elements=['ticker', 'date'], set_=update_dict)
            db.execute(stmt)
        
        # --- 4. AI TRAINING ---
        ai_df = data_with_ta.reset_index().rename(columns={
            'Date': 'date', 'Close': 'close', 'Volume': 'volume',
            'Open': 'open', 'High': 'high', 'Low': 'low'
        })
        
        if len(ai_df) > 50:
            print(f"ASTRA: Training AI models for {ticker}...")
            prophet_model, forecast = train_prophet_model(ai_df, ticker)
            rf_model, confidence = train_classifier_model(ai_df, ticker)
            
            # --- 5. CALCULATE FUNDAMENTALS (NEW) ---
            funda_dict = calculate_advanced_fundamentals(t)
            
            # --- 6. RULES ENGINE ---
            latest_row = data_with_ta.iloc[-1]
            atr_val = latest_row.get('atr', latest_row['Close'] * 0.02)
            if pd.isna(atr_val): atr_val = latest_row['Close'] * 0.02

            analysis_result = analyze_stock(
                ticker, 
                current_price=float(latest_row['Close']),
                rsi=float(latest_row['rsi']),
                macd=float(latest_row['macd']),
                ema_50=float(latest_row['ema_50']),
                atr=float(atr_val),
                ai_confidence=float(confidence),
                prophet_forecast=forecast,
                fundamentals=funda_dict # Pass the new metrics
            )
            
            # --- 7. SAVE VERDICT & FUNDAMENTALS ---
            info = t.info
            existing_funda = db.query(FundamentalData).filter(FundamentalData.ticker == ticker).first()
            
            data_dict = {
                "company_name": info.get('longName', ticker),
                "sector": info.get('sector', 'Unknown'),
                "industry": info.get('industry', 'Unknown'),
                "market_cap": float(info.get('marketCap', 0)),
                "pe_ratio": float(info.get('trailingPE', 0)),
                "eps": float(info.get('trailingEps', 0)),
                "beta": float(info.get('beta', 0)),
                
                # NEW FUNDAMENTAL COLUMNS
                "roe": float(funda_dict['roe']),
                "debt_to_equity": float(funda_dict['debt_to_equity']),
                "free_cash_flow": float(funda_dict['free_cash_flow']),
                "revenue_growth": float(funda_dict['revenue_growth']),
                
                "st_verdict": analysis_result['st']['verdict'],
                "st_target": float(analysis_result['st']['target']),
                "st_stoploss": float(analysis_result['st']['sl']),
                "mt_verdict": analysis_result['mt']['verdict'],
                "mt_target": float(analysis_result['mt']['target']),
                "mt_stoploss": float(analysis_result['mt']['sl']),
                "lt_verdict": analysis_result['lt']['verdict'],
                "lt_target": float(analysis_result['lt']['target']),
                "lt_stoploss": float(analysis_result['lt']['sl']),
                "ai_reasoning": analysis_result['reasoning'],
                "ai_confidence": float(analysis_result['ai_confidence']), 
                "last_updated": datetime.now().date()
            }

            if existing_funda:
                for key, value in data_dict.items(): setattr(existing_funda, key, value)
            else:
                db.add(FundamentalData(ticker=ticker, **data_dict))

            db.commit()
            print(f"ASTRA: DONE {ticker}. Verdict: {analysis_result['st']['verdict']}")
            return True
        else:
            print(f"ASTRA: Not enough data to train for {ticker}")
            return False

    except Exception as e:
        db.rollback()
        print(f"ASTRA: ERROR processing {ticker}: {e}")
        return False

@app.task(name="astra.run_nightly_update")
def run_nightly_update():
    print("ASTRA: Starting Nightly Update...")
    db = SessionLocal()
    for ticker in NIFTY50_TICKERS:
        process_one_stock(ticker, db)
        time.sleep(1)
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
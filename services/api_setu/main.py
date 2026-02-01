from fastapi import FastAPI, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from shared.database import get_db, FundamentalData, StockData
from schemas import AnalysisResponse, ScreenerResponse
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD, EMAIndicator
import pandas as pd
from datetime import date
import os
from celery import Celery
from typing import List, Dict, Any
import logging
import traceback

app = FastAPI(title="Setu API - Project Gyan")
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
# Added 'backend' to enable result retrieval
celery_app = Celery('api_sender', broker=REDIS_URL, backend=REDIS_URL)

@app.get("/backtest/{ticker}")
async def run_backtest(ticker: str):
    """
    Triggers a backtest simulation for the ticker.
    Returns a Task ID immediately. Use /backtest/status/{task_id} to check results.
    """
    ticker = ticker.strip().upper()
    logging.info(f"API: Requesting Backtest for {ticker}...")
    
    # Trigger Task
    # We use a fixed date range for the demo: Jan 1 2025 to April 1 2025
    task = celery_app.send_task(
        "astra.run_backtest", 
        args=[ticker, "2025-01-01", "2025-04-01"],
        queue="astra_q"
    )
    
    return {
        "status": "submitted", 
        "message": "Backtest started", 
        "task_id": task.id
    }

@app.get("/backtest/status/{task_id}")
async def get_backtest_status(task_id: str):
    """
    Checks the status of a backtest task.
    """
    try:
        result = celery_app.AsyncResult(task_id)
        if result.ready():
            return {
                "status": "completed",
                "result": result.get()
            }
        else:
            return {"status": "pending"}
    except Exception as e:
        logging.error(f"Status Check Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to check status")

@app.get("/")
def read_root():
    return {"status": "Setu is online", "project": "Gyan"}

@app.get("/analysis/{ticker}", response_model=AnalysisResponse)
def get_stock_analysis(ticker: str, db: Session = Depends(get_db)):
    
    # Fix input
    ticker = ticker.strip().upper()
    
    # 1. Try Database First
    funda = db.query(FundamentalData).filter(FundamentalData.ticker == ticker).first()
    
    # Check if data is stale (older than today)
    is_stale = False
    if funda and funda.last_updated:
        if funda.last_updated < date.today():
            is_stale = True
    
    # If missing or stale, trigger background update
    if not funda or is_stale:
        logging.info(f"API: Triggering background update for {ticker}...")
        celery_app.send_task("astra.run_single_stock_update", args=[ticker], queue="astra_q")

    if funda:
        # Get Latest Technicals
        tech = db.query(StockData).filter(StockData.ticker == ticker).order_by(StockData.date.desc()).first()
        
        # Get Live Price (Fast)
        live_price = 0.0
        try:
            live = yf.Ticker(ticker).history(period="1d")
            if not live.empty:
                live_price = live['Close'].iloc[-1]
        except: pass
        
        # Fallback if live fetch fails
        if live_price == 0.0 and tech: 
            live_price = tech.close
            
        return {
            "ticker": funda.ticker,
            "company_name": funda.company_name or ticker,
            "sector": funda.sector or "Unknown",
            "current_price": live_price,
            
            # Map DB columns to Nested Schema
            "st": {"verdict": funda.st_verdict, "target": funda.st_target, "sl": funda.st_stoploss},
            "mt": {"verdict": funda.mt_verdict, "target": funda.mt_target, "sl": funda.mt_stoploss},
            "lt": {"verdict": funda.lt_verdict, "target": funda.lt_target, "sl": funda.lt_stoploss},
            
            "verdict": funda.ai_verdict, # Legacy support
            "confidence": funda.ai_confidence,
            "target_price": funda.target_price,
            "reasoning": funda.ai_reasoning,
            "last_updated": funda.last_updated,
            "rsi": tech.rsi if tech else 0,
            "macd": tech.macd if tech else 0,
            "source": "database"
        }

    # 2. Instant Analysis (Fallback if not in DB yet)
    print(f"API: {ticker} not in DB. Running Light Live Analysis...")
    
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1y") 
        
        if hist.empty:
            raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found on Yahoo Finance.")

        current = hist['Close'].iloc[-1]
        rsi_series = RSIIndicator(hist['Close']).rsi()
        ema_series = EMAIndicator(hist['Close'], window=50).ema_indicator()
        
        rsi = rsi_series.iloc[-1]
        ema = ema_series.iloc[-1]
        
        # --- HONEST MODE: DO NOT GUESS ---
        # Instead of guessing HOLD/BUY, we return WAITING.
        verdict = "WAITING"
        
        return {
            "ticker": ticker,
            "company_name": t.info.get('longName', ticker),
            "sector": t.info.get('sector', "Unknown"),
            "current_price": current,
            "st": {"verdict": verdict, "target": 0.0, "sl": 0.0},
            "mt": {"verdict": verdict, "target": 0.0, "sl": 0.0},
            "lt": {"verdict": verdict, "target": 0.0, "sl": 0.0},
            "verdict": verdict,
            "confidence": 0.0, 
            "target_price": 0.0,
            "reasoning": "⚡ **ANALYSIS IN PROGRESS...**\n\nThe AI is currently crunching 2 years of data, balance sheets, and risk models. This takes about 30-60 seconds.\n\n**PLEASE WAIT AND REFRESH** to get the true Deep Analysis. Do not trade yet.",
            "last_updated": date.today(),
            "rsi": rsi,
            "macd": 0.0,
            "source": "live"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        logging.error(f"API Error: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Live analysis failed: {str(e)}")


@app.get("/screener/{horizon}", response_model=list[ScreenerResponse])
def get_screener_signals(horizon: str, db: Session = Depends(get_db)):
    """
    Returns the TOP opportunities for a specific horizon (short/mid/long).
    """
    if horizon == "short":
        verdict_col = FundamentalData.st_verdict
        target_col = FundamentalData.st_target
        sl_col = FundamentalData.st_stoploss
        days_col = FundamentalData.st_days
        default_days = 14
    elif horizon == "mid":
        verdict_col = FundamentalData.mt_verdict
        target_col = FundamentalData.mt_target
        sl_col = FundamentalData.mt_stoploss
        days_col = FundamentalData.mt_days
        default_days = 60
    elif horizon == "long":
        verdict_col = FundamentalData.lt_verdict
        target_col = FundamentalData.lt_target
        sl_col = FundamentalData.lt_stoploss
        days_col = FundamentalData.lt_days
        default_days = 365
    else:
        raise HTTPException(status_code=400, detail=f"Invalid horizon '{horizon}'. Use: short, mid, long")

    # Filter by 'BUY', 'ACCUMULATE', and 'STRONG BUY'
    # We fetch ALL and sort in Python to handle calculated fields like 'upside'
    results = db.query(FundamentalData).filter(
        verdict_col.in_(['BUY', 'ACCUMULATE', 'STRONG BUY'])
    ).all()
    
    screener_data = []
    
    for r in results:
        # Optimization: Fetch price from DB Technicals instead of Live if speed is key
        # For screener, speed >> live precision.
        tech = db.query(StockData).filter(StockData.ticker == r.ticker).order_by(StockData.date.desc()).first()
        curr_price = tech.close if tech else 0.0
        
        tgt = getattr(r, target_col.name)
        sl = getattr(r, sl_col.name)
        vld_days = getattr(r, days_col.name) or default_days
        verdict = getattr(r, verdict_col.name)
        
        upside = 0.0
        if curr_price > 0 and tgt:
            upside = ((tgt - curr_price) / curr_price) * 100
        
        # --- HORIZON SPECIFIC FILTERING ---
        if horizon == "long":
            # Quality Filter: Discard Junk for Long Term
            # F-Score < 5 means deteriorating fundamentals.
            if r.piotroski_f_score is not None and r.piotroski_f_score < 5:
                continue
                
        # Append to list
        screener_data.append({
            "ticker": r.ticker,
            "company_name": r.company_name,
            "current_price": curr_price,
            "verdict": verdict,
            "confidence": r.ai_confidence,
            "target_price": tgt,
            "stop_loss": sl,
            "upside_pct": round(upside, 2),
            "duration_days": vld_days,
            "reasoning": r.ai_reasoning,
            # Internal helpers for sorting
            "_f_score": r.piotroski_f_score or 0
        })
    
    # --- SORTING LOGIC ---
    if horizon == "long":
        # Sort by Quality (F-Score) weighted heavily with Upside
        # We want High Quality stocks that also have upside.
        screener_data.sort(key=lambda x: (x['_f_score'] * 10) + x['upside_pct'], reverse=True)
    else:
        # Short/Mid Term: Momentum rules. Pure Upside.
        screener_data.sort(key=lambda x: x['upside_pct'], reverse=True)
        
    return screener_data[:20]
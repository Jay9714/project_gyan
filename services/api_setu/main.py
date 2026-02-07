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
import redis
import json

app = FastAPI(title="Setu API - Project Gyan")
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
# Added 'backend' to enable result retrieval
celery_app = Celery('api_sender', broker=REDIS_URL, backend=REDIS_URL)

# Redis Client for Bot State
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

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
            
        # Helper: Calculate derived fields
        def get_details(term, verdict, target, sl, price):
            # Aggressive Target Heuristic (since not in DB)
            # If Verdict is BUY, T2 is higher. If SELL, T2 is lower.
            t_agg = target
            if verdict in ["BUY", "STRONG BUY", "ACCUMULATE"]:
                t_agg = target * 1.05 # +5% beyond conservative
            elif verdict == "SELL":
                t_agg = target * 0.95
                
            # RR
            risk = abs(price - sl) if sl else 1.0
            reward = abs(target - price) if target else 0.0
            rr = f"1:{reward/risk:.1f}" if risk > 0 else "1:1"
            
            return {
                "verdict": verdict, 
                "target": target, 
                "target_agg": round(t_agg, 2),
                "sl": sl,
                "rr": rr
            }

        # Risk Badge
        risk_score = funda.score_risk or 50.0
        risk_level = "MEDIUM"
        if risk_score <= 30: risk_level = "LOW"
        elif risk_score >= 70: risk_level = "HIGH"

        return {
            "ticker": funda.ticker,
            "company_name": funda.company_name or ticker,
            "sector": funda.sector or "Unknown",
            "current_price": live_price,
            
            # Map DB columns to Nested Schema
            "st": get_details("short", funda.st_verdict, funda.st_target, funda.st_stoploss, live_price),
            "mt": get_details("mid", funda.mt_verdict, funda.mt_target, funda.mt_stoploss, live_price),
            "lt": get_details("long", funda.lt_verdict, funda.lt_target, funda.lt_stoploss, live_price),
            
            "verdict": funda.ai_verdict, # Legacy support
            "confidence": funda.ai_confidence,
            "risk_level": risk_level,
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
            "st": {"verdict": verdict, "target": 0.0, "sl": 0.0, "target_agg": 0.0, "rr": "N/A"},
            "mt": {"verdict": verdict, "target": 0.0, "sl": 0.0, "target_agg": 0.0, "rr": "N/A"},
            "lt": {"verdict": verdict, "target": 0.0, "sl": 0.0, "target_agg": 0.0, "rr": "N/A"},
            "verdict": verdict,
            "confidence": 0.0, 
            "risk_level": "WAITING", # Added missing field
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



# --------------------------------------------------------------------------------
# DISABLED ENDPOINTS (Stock Finder & Auto-Trade) - FOCUS: DEEP ANALYSIS
# --------------------------------------------------------------------------------
# To re-enable, uncomment the code below or restore from version history.

# @app.get("/screener/{horizon}", response_model=list[ScreenerResponse])
# def get_screener_signals(horizon: str, db: Session = Depends(get_db)):
#     """
#     Returns the TOP opportunities for a specific horizon (short/mid/long).
#     """
#     ... (Code Removed to simplify focus) ... 
#     return []

# @app.get("/bot/status")
# def get_bot_status():
#     return {"active": False, "message": "Bot Disabled"}

# @app.post("/bot/start")
# def start_bot():
#     return {"status": "disabled"}

# @app.post("/bot/stop")
# def stop_bot():
#     return {"status": "disabled"}

# @app.get("/bot/trades")
# def get_bot_trades():
#     return []


from fastapi import FastAPI, Depends, HTTPException
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

# NOTE: We do NOT import news_analysis here to avoid heavy dependencies in the API.

app = FastAPI(title="Setu API - Project Gyan")
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
celery_app = Celery('api_sender', broker=REDIS_URL)

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
        print(f"API: Triggering background update for {ticker}...")
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
        
        # Simple Logic
        verdict = "BUY" if rsi < 40 and current > ema else "SELL" if rsi > 70 else "HOLD"
        
        return {
            "ticker": ticker,
            "company_name": t.info.get('longName', ticker),
            "sector": t.info.get('sector', "Unknown"),
            "current_price": current,
            "st": {"verdict": verdict, "target": current * 1.05, "sl": current * 0.95},
            "mt": {"verdict": verdict, "target": current * 1.10, "sl": current * 0.90},
            "lt": {"verdict": verdict, "target": current * 1.20, "sl": current * 0.85},
            "verdict": verdict,
            "confidence": 0.5, # 50% for basic analysis
            "target_price": current * 1.10,
            "reasoning": f"Instant Analysis (Deep analysis running in background). RSI={rsi:.1f}",
            "last_updated": date.today(),
            "rsi": rsi,
            "macd": 0.0,
            "source": "live"
        }
        
    except HTTPException as he:
        raise he
    except Exception as e:
        print(f"API Error: {e}")
        raise HTTPException(status_code=500, detail=f"Live analysis failed: {str(e)}")


# --- UPDATED SCREENER LOGIC (Fixes 404 Error) ---
@app.get("/screener/{horizon}", response_model=list[ScreenerResponse])
def get_screener_signals(horizon: str, db: Session = Depends(get_db)):
    """
    Returns the TOP opportunities for a specific horizon (short/mid/long).
    """
    # 1. Map horizon to database columns
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

    # 2. Query DB: Filter by 'BUY' verdict and Sort by AI Confidence
    # We look for 'BUY' or 'ACCUMULATE'
    results = db.query(FundamentalData).filter(
        verdict_col.in_(['BUY', 'ACCUMULATE'])
    ).order_by(FundamentalData.ai_confidence.desc()).limit(20).all()
    
    screener_data = []
    
    for r in results:
        # Get Price for Upside Calc
        tech = db.query(StockData).filter(StockData.ticker == r.ticker).order_by(StockData.date.desc()).first()
        curr_price = tech.close if tech else 0.0
        
        # Get dynamic target based on the chosen horizon
        tgt = getattr(r, target_col.name)
        sl = getattr(r, sl_col.name)
        vld_days = getattr(r, days_col.name) or default_days
        verdict = getattr(r, verdict_col.name)
        
        upside = 0.0
        if curr_price > 0 and tgt:
            upside = ((tgt - curr_price) / curr_price) * 100
            
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
            "reasoning": r.ai_reasoning
        })
        
    return screener_data
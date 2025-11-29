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

# NOTE: We do NOT import news_analysis here to avoid heavy dependencies.

app = FastAPI(title="Setu API - Project Gyan")
REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
celery_app = Celery('api_sender', broker=REDIS_URL)

@app.get("/")
def read_root():
    return {"status": "Setu is online", "project": "Gyan"}

@app.get("/analysis/{ticker}", response_model=AnalysisResponse)
def get_stock_analysis(ticker: str, db: Session = Depends(get_db)):
    ticker = ticker.strip().upper()
    funda = db.query(FundamentalData).filter(FundamentalData.ticker == ticker).first()
    
    if funda:
        tech = db.query(StockData).filter(StockData.ticker == ticker).order_by(StockData.date.desc()).first()
        live_price = 0.0
        try:
            live = yf.Ticker(ticker).history(period="1d")
            if not live.empty: live_price = live['Close'].iloc[-1]
        except: pass
        if not live_price and tech: live_price = tech.close
            
        return {
            "ticker": funda.ticker, "company_name": funda.company_name, "sector": funda.sector,
            "current_price": live_price,
            "st": {"verdict": funda.st_verdict, "target": funda.st_target, "sl": funda.st_stoploss},
            "mt": {"verdict": funda.mt_verdict, "target": funda.mt_target, "sl": funda.mt_stoploss},
            "lt": {"verdict": funda.lt_verdict, "target": funda.lt_target, "sl": funda.lt_stoploss},
            "verdict": funda.ai_verdict, "confidence": funda.ai_confidence, "target_price": funda.target_price,
            "reasoning": funda.ai_reasoning, "last_updated": funda.last_updated,
            "rsi": tech.rsi if tech else 0, "macd": tech.macd if tech else 0, "source": "database"
        }

    # 2. Instant Analysis (Fallback)
    print(f"API: {ticker} not in DB. Running Light Live Analysis...")
    celery_app.send_task("astra.run_single_stock_update", args=[ticker], queue="astra_q")

    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="1y") 
        if hist.empty: raise HTTPException(status_code=404, detail=f"Ticker '{ticker}' not found.")

        current = hist['Close'].iloc[-1]
        rsi = RSIIndicator(hist['Close']).rsi().iloc[-1]
        ema = EMAIndicator(hist['Close'], window=50).ema_indicator().iloc[-1]
        
        # Simple Logic (No News)
        verdict = "BUY" if rsi < 40 and current > ema else "SELL" if rsi > 70 else "HOLD"
        
        return {
            "ticker": ticker, "company_name": t.info.get('longName', ticker), "sector": t.info.get('sector', "Unknown"),
            "current_price": current,
            "st": {"verdict": verdict, "target": current * 1.05, "sl": current * 0.95},
            "mt": {"verdict": verdict, "target": current * 1.10, "sl": current * 0.90},
            "lt": {"verdict": verdict, "target": current * 1.20, "sl": current * 0.85},
            "verdict": verdict, "confidence": 50.0, "target_price": current * 1.10,
            "reasoning": f"Instant Analysis (Price Action Only). RSI={rsi:.1f}", 
            "last_updated": date.today(), "rsi": rsi, "macd": 0.0, "source": "live"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Live analysis failed: {str(e)}")
    
    # ... (Screener endpoint same) ...
    @app.get("/screener/buy", response_model=list[ScreenerResponse])
    def get_buy_signals(db: Session = Depends(get_db)):
        results = db.query(FundamentalData).filter(
            FundamentalData.st_verdict.in_(['BUY', 'ACCUMULATE'])
        ).order_by(FundamentalData.ai_confidence.desc()).limit(20).all()
        return [
            {"ticker": r.ticker, "verdict": r.st_verdict, "confidence": r.ai_confidence,
             "target_price": r.st_target, "reasoning": r.ai_reasoning} for r in results
        ]
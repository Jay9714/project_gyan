from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db, FundamentalData, StockData
from schemas import AnalysisResponse, ScreenerResponse
import yfinance as yf

app = FastAPI(title="Setu API - Project Gyan")

@app.get("/")
def read_root():
    return {"status": "Setu is online", "project": "Gyan"}

@app.get("/analysis/{ticker}", response_model=AnalysisResponse)
def get_stock_analysis(ticker: str, db: Session = Depends(get_db)):
    # 1. Get AI Verdict from DB
    funda = db.query(FundamentalData).filter(FundamentalData.ticker == ticker).first()
    
    if not funda:
        raise HTTPException(status_code=404, detail="Stock not found in database. Run Nightly Hunt first.")

    # 2. Get Latest Technicals from DB
    tech = db.query(StockData).filter(StockData.ticker == ticker).order_by(StockData.date.desc()).first()

    # 3. Get Live Price
    try:
        live_price = yf.Ticker(ticker).history(period="1d")['Close'].iloc[-1]
    except:
        live_price = 0.0

    return {
        "ticker": funda.ticker,
        "company_name": funda.company_name,
        "sector": funda.sector,
        "current_price": live_price,
        "verdict": funda.ai_verdict,
        "confidence": funda.ai_confidence,
        "target_price": funda.target_price,
        "reasoning": funda.ai_reasoning,
        "last_updated": funda.last_updated,
        "rsi": tech.rsi if tech else 0,
        "macd": tech.macd if tech else 0
    }

@app.get("/screener/buy", response_model=list[ScreenerResponse])
def get_buy_signals(db: Session = Depends(get_db)):
    results = db.query(FundamentalData).filter(
        FundamentalData.ai_verdict == "BUY"
    ).order_by(FundamentalData.ai_confidence.desc()).limit(10).all()
    
    return [
        {
            "ticker": r.ticker,
            "verdict": r.ai_verdict,
            "confidence": r.ai_confidence,
            "target_price": r.target_price,
            "reasoning": r.ai_reasoning
        }
        for r in results
    ]
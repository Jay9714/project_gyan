import yfinance as yf
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from shared.database import SectorPerformance

# Mapping of Yahoo Finance Tickers for Indian Sectors
SECTOR_INDICES = {
    "Banking": "^NSEBANK",
    "Auto": "^CNXAUTO",
    "Financial Services": "^CNXFIN",
    "FMCG": "^CNXFMCG",
    "IT": "^CNXIT",
    "Media": "^CNXMEDIA",
    "Metal": "^CNXMETAL",
    "Pharma": "^CNXPHARMA",
    "PSU Bank": "^CNXPSUBANK",
    "Private Bank": "^CNXPVTBANK",
    "Real Estate": "^CNXREALTY",
    "Consumer Durables": "^CNXCONSUM",
    "Energy": "^CNXENERGY",
    "Infra": "^CNXINFRA"
}

def update_sector_trends(db: Session):
    """
    Fetches data for all major sectors and updates their trend status in DB.
    """
    print("SECTOR: Starting Sector Pulse Check...")
    
    today = datetime.now().date()
    
    for sector_name, ticker in SECTOR_INDICES.items():
        try:
            # Fetch 6 months of data
            data = yf.download(ticker, period="6mo", interval="1d", progress=False)
            
            if data.empty or len(data) < 50:
                print(f"SECTOR: No data for {sector_name}")
                continue
                
            # Calculate Trend Indicators
            close = data['Close']
            
            # 1. Moving Averages
            sma_50 = close.rolling(window=50).mean().iloc[-1]
            sma_200 = close.rolling(window=200).mean().iloc[-1] if len(data) > 200 else sma_50
            current_price = close.iloc[-1]
            
            # 2. RSI (Simplified)
            delta = close.diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=13, adjust=False).mean()
            ema_down = down.ewm(com=13, adjust=False).mean()
            rs = ema_up / ema_down
            rsi = 100 - (100 / (1 + rs)).iloc[-1]
            
            # 3. Determine Status
            score = 50
            
            # Trend Score
            if current_price > sma_50: score += 20
            if sma_50 > sma_200: score += 10
            
            # Momentum Score
            if rsi > 50: score += 10
            if rsi > 70: score -= 10 # Overbought
            if rsi < 30: score -= 10 # Oversold (Panic)
            
            # Status Logic
            status = "NEUTRAL"
            if score >= 70: status = "BULLISH"
            elif score <= 40: status = "BEARISH"
            
            # Save to DB
            existing = db.query(SectorPerformance).filter(SectorPerformance.sector_name == sector_name).first()
            if existing:
                existing.trend_score = float(score)
                existing.status = status
                existing.last_updated = today
            else:
                db.add(SectorPerformance(
                    sector_name=sector_name,
                    trend_score=float(score),
                    status=status,
                    last_updated=today
                ))
            
            print(f"SECTOR: {sector_name} -> {status} (Score: {score})")
            
        except Exception as e:
            print(f"SECTOR: Error updating {sector_name}: {e}")
            
    db.commit()
    print("SECTOR: Update Complete.")
import yfinance as yf
import pandas as pd
from datetime import datetime
from sqlalchemy.orm import Session
from shared.database import SectorPerformance

# Mapping of Yahoo Finance Tickers for Indian Sectors
# Updated to remove broken indices and use reliable ones
SECTOR_INDICES = {
    # Core Sectors (High Reliability)
    "Banking": "^NSEBANK",
    "Auto": "^CNXAUTO",
    "FMCG": "^CNXFMCG",
    "IT": "^CNXIT",
    "Media": "^CNXMEDIA",
    "Metal": "^CNXMETAL",
    "Pharma": "^CNXPHARMA",
    "PSU Bank": "^CNXPSUBANK",
    "Real Estate": "^CNXREALTY",
    "Energy": "^CNXENERGY",
    "Infra": "^CNXINFRA",
    
    # Validated Additional Sectors
    "Financial Services": "NIFTY_FIN_SERVICE.NS", 
    "Private Bank": "NIFTY_PVT_BANK.NS",        
    
    # Removed ^CNXHEALTH as it causes 404s. 
    # Removed ^CNXSERVICE as it is often empty.
    
    # Broader Markets
    "Nifty 50": "^NSEI",                        
    "Nifty Next 50": "^NSMIDCP"                 
}

def update_sector_trends(db: Session):
    """
    Fetches data for all major sectors and updates their trend status in DB.
    Handles newer yfinance MultiIndex return format.
    """
    print("SECTOR: Starting Sector Pulse Check...")
    
    today = datetime.now().date()
    
    for sector_name, ticker in SECTOR_INDICES.items():
        try:
            # Fetch 6 months of data
            # auto_adjust=True fixes some data issues
            data = yf.download(ticker, period="6mo", interval="1d", progress=False, auto_adjust=True)
            
            # 1. Fix MultiIndex if present (yfinance v0.2+ often returns MultiIndex columns)
            if isinstance(data.columns, pd.MultiIndex):
                # If columns are like ('Close', '^NSEBANK'), flatten them or select the ticker level
                try:
                    data = data.xs(ticker, axis=1, level=1)
                except:
                    # Fallback: just drop the top level if it's generic
                    data.columns = data.columns.get_level_values(0)

            # 2. Check for empty data safely
            if data.empty or len(data) < 50:
                print(f"SECTOR: No data for {sector_name} ({ticker})")
                continue
            
            # Ensure 'Close' column exists (case-insensitive check)
            col_map = {c.lower(): c for c in data.columns}
            if 'close' not in col_map:
                print(f"SECTOR: Missing 'Close' column for {sector_name}")
                continue
                
            close = data[col_map['close']].astype(float)

            # 3. Calculations
            sma_50 = close.rolling(window=50).mean().iloc[-1]
            sma_200 = close.rolling(window=200).mean().iloc[-1] if len(data) > 200 else sma_50
            current_price = close.iloc[-1]
            
            # RSI Calculation
            delta = close.diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ema_up = up.ewm(com=13, adjust=False).mean()
            ema_down = down.ewm(com=13, adjust=False).mean()
            rs = ema_up / ema_down
            rsi_val = 100 - (100 / (1 + rs)).iloc[-1]
            
            # 4. Scoring Logic
            score = 50
            
            if current_price > sma_50: score += 20
            if sma_50 > sma_200: score += 10
            
            if rsi_val > 50: score += 10
            if rsi_val > 70: score -= 10
            if rsi_val < 30: score -= 10
            
            status = "NEUTRAL"
            if score >= 70: status = "BULLISH"
            elif score <= 40: status = "BEARISH"
            
            # 5. Save to DB
            # Task 2.1: Fetch Sector PE
            sector_t = yf.Ticker(ticker)
            try: 
                 sector_pe = float(sector_t.info.get('trailingPE', 0.0))
            except: 
                 sector_pe = 0.0

            existing = db.query(SectorPerformance).filter(SectorPerformance.sector_name == sector_name).first()
            if existing:
                existing.trend_score = float(score)
                existing.status = status
                existing.sector_pe = sector_pe
                existing.last_updated = today
            else:
                db.add(SectorPerformance(
                    sector_name=sector_name,
                    trend_score=float(score),
                    status=status,
                    sector_pe=sector_pe,
                    last_updated=today
                ))
            
            print(f"SECTOR: {sector_name} -> {status} (Score: {score})")
            
        except Exception as e:
            # Catch-all to prevent one sector failure from stopping the loop
            print(f"SECTOR: Error updating {sector_name}: {str(e)}")
            
    db.commit()
    print("SECTOR: Update Complete.")
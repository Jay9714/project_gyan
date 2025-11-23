from pydantic import BaseModel
from datetime import date
from typing import Optional

class HorizonData(BaseModel):
    verdict: Optional[str]
    target: Optional[float]
    sl: Optional[float]

class AnalysisResponse(BaseModel):
    ticker: str
    company_name: str
    sector: Optional[str]
    current_price: float
    
    st: Optional[HorizonData]
    mt: Optional[HorizonData]
    lt: Optional[HorizonData]

    verdict: Optional[str]
    confidence: Optional[float]
    target_price: Optional[float]
    reasoning: Optional[str]
    last_updated: Optional[date]
    rsi: Optional[float]
    macd: Optional[float]
    source: Optional[str]

# --- UPDATED SCREENER RESPONSE ---
class ScreenerResponse(BaseModel):
    ticker: str
    company_name: str # Added
    current_price: float # Added
    verdict: Optional[str]
    confidence: Optional[float]
    target_price: Optional[float]
    stop_loss: Optional[float] # Added
    upside_pct: float # Added
    duration_days: int # Added
    reasoning: Optional[str]
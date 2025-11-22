from pydantic import BaseModel
from datetime import date
from typing import Optional

class AnalysisResponse(BaseModel):
    ticker: str
    company_name: str
    sector: str | None
    current_price: float
    # AI Data
    verdict: str | None
    confidence: float | None
    target_price: float | None
    reasoning: str | None
    last_updated: date | None
    # Technicals
    rsi: float | None
    macd: float | None

class ScreenerResponse(BaseModel):
    ticker: str
    verdict: str
    confidence: float
    target_price: float
    reasoning: str
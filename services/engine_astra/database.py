import os
from sqlalchemy import create_engine, Column, String, Float, Integer, Date, UniqueConstraint
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:admin@db:5432/gyan_db')

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class StockData(Base):
    __tablename__ = "stock_data"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    date = Column(Date, index=True, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)
    
    # TA Columns
    rsi = Column(Float)
    macd = Column(Float)
    macd_signal = Column(Float)
    ema_50 = Column(Float)
    ema_200 = Column(Float)
    
    __table_args__ = (UniqueConstraint('ticker', 'date', name='_ticker_date_uc'),)


class FundamentalData(Base):
    __tablename__ = "fundamental_data"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, unique=True, nullable=False)
    
    # Basic Info
    company_name = Column(String)
    sector = Column(String)
    industry = Column(String)
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    eps = Column(Float)
    beta = Column(Float)
    
    # --- NEW COLUMNS FOR PHASE 4 (AI RESULTS) ---
    ai_verdict = Column(String)        # "BUY", "SELL", "HOLD"
    ai_confidence = Column(Float)      # 0.0 to 100.0
    target_price = Column(Float)       # Prophet Prediction (30 days)
    ai_reasoning = Column(String)      # "RSI Oversold | AI Predicts +10%"
    last_updated = Column(Date)        # When did this analysis run?
    # --------------------------------------------

def create_db_and_tables():
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables created/updated.")
    except Exception as e:
        print(f"Error creating database tables: {e}")
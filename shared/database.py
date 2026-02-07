import os
from sqlalchemy import create_engine, Column, String, Float, Integer, Date, DateTime, UniqueConstraint, Boolean
from datetime import datetime
from sqlalchemy.orm import sessionmaker, declarative_base

# Task 3.1: Enhanced Schema
# Added instrument_type, selected_algo, interval, start_time, square_off_time to TradeTable.

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:admin@db:5432/gyan_db')

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class StockData(Base):
    __tablename__ = "stock_data"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    date = Column(Date, index=True, nullable=False)
    open = Column(Float); high = Column(Float); low = Column(Float); close = Column(Float); volume = Column(Integer)
    rsi = Column(Float); macd = Column(Float); macd_signal = Column(Float)
    ema_50 = Column(Float); ema_200 = Column(Float); atr = Column(Float)
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
    
    # Advanced Risk Metrics
    piotroski_f_score = Column(Integer, default=5) 
    altman_z_score = Column(Float, default=3.0)    
    beneish_m_score = Column(Float, default=-2.0)  
    
    # Component Scores (0-100)
    score_fundamental = Column(Float, default=50.0)
    score_technical = Column(Float, default=50.0)
    score_growth = Column(Float, default=50.0)
    score_risk = Column(Float, default=50.0)
    score_news = Column(Float, default=50.0)
    
    # Predictions
    st_verdict = Column(String); st_target = Column(Float); st_stoploss = Column(Float); st_days = Column(Integer)
    mt_verdict = Column(String); mt_target = Column(Float); mt_stoploss = Column(Float); mt_days = Column(Integer)
    lt_verdict = Column(String); lt_target = Column(Float); lt_stoploss = Column(Float); lt_days = Column(Integer)

    ai_verdict = Column(String)
    ai_confidence = Column(Float)
    target_price = Column(Float)
    ai_reasoning = Column(String)
    last_updated = Column(Date)
    
    # MAX POWER COLUMNS
    predicted_close = Column(Float)
    ensemble_score = Column(Float)


class Trade(Base):
    """
    Task 3.1 Enhanced Trade Schema.
    Used for persistent OMS tracking.
    """
    __tablename__ = "trades"
    uuid = Column(String, primary_key=True, index=True)
    ticker = Column(String, index=True)
    instrument_type = Column(String, default="EQUITY_INTRADAY")
    
    direction = Column(String) # BUY/SELL
    entry_price = Column(Float)
    quantity = Column(Integer)
    
    sl_price = Column(Float)
    tp_price = Column(Float)
    
    status = Column(String) # PENDING, OPEN, CLOSED, FAILED
    
    # AI Metadata
    selected_algo = Column(String)
    interval = Column(String)
    indicators_used = Column(String)
    reasoning = Column(String)
    
    # Times (Enhanced)
    entry_time = Column(DateTime, default=datetime.utcnow)
    exit_time = Column(DateTime)
    start_time = Column(DateTime)    # AI Scheduled Start
    square_off_time = Column(DateTime) # Auto-Liquidation Time
    
    pnl = Column(Float)


class SectorPerformance(Base):
    __tablename__ = "sector_performance"
    id = Column(Integer, primary_key=True, index=True)
    sector_name = Column(String, unique=True, index=True)
    trend_score = Column(Float)
    status = Column(String)
    last_updated = Column(Date)

class CatalystEvent(Base):
    __tablename__ = "catalyst_events"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    score = Column(Integer, default=0) 
    context = Column(String)
    created_at = Column(Date, default=datetime.now().date)
    is_active = Column(Boolean, default=True)


def create_db_and_tables():
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables created/updated.")
    except Exception as e:
        print(f"Error creating database tables: {e}")


def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
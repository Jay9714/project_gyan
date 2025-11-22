import os
from sqlalchemy import create_engine, Column, String, Float, Integer, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:admin@db:5432/gyan_db')

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# We define the SAME models here so the API can read them
class FundamentalData(Base):
    __tablename__ = "fundamental_data"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, unique=True)
    company_name = Column(String)
    sector = Column(String)
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    # AI Results
    ai_verdict = Column(String)
    ai_confidence = Column(Float)
    target_price = Column(Float)
    ai_reasoning = Column(String)
    last_updated = Column(Date)

class StockData(Base):
    __tablename__ = "stock_data"
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True)
    date = Column(Date, index=True)
    close = Column(Float)
    rsi = Column(Float)
    macd = Column(Float)
    ema_50 = Column(Float)

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
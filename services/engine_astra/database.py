# services/engine_astra/database.py
import os
from sqlalchemy import create_engine, Column, String, Float, Integer, Date, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Get the database URL from the environment variable we set in docker-compose
DATABASE_URL = os.environ.get('DATABASE_URL')

# SQLAlchemy setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- Define Our Database Tables ---

class StockData(Base):
    """
    Table to store the daily OHLCV (Open, High, Low, Close, Volume) price data.
    """
    __tablename__ = "stock_data"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    date = Column(Date, index=True, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Integer)

    # Create a "composite unique constraint"
    # This prevents us from ever saving two rows for the same stock on the same day
    __table_args__ = (UniqueConstraint('ticker', 'date', name='_ticker_date_uc'),)


class FundamentalData(Base):
    """
    Table to store fundamental data. We will add more to this in Phase 3.
    """
    __tablename__ = "fundamental_data"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, unique=True, nullable=False)
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    eps = Column(Float)
    # We will add sentiment, RSI, MACD, and AI predictions here later

# --- Utility Function ---
def create_db_and_tables():
    """
    This function will be called by the worker to create the tables
    if they don't already exist.
    """
    try:
        Base.metadata.create_all(bind=engine)
        print("Database tables created (if they didn't exist).")
    except Exception as e:
        print(f"Error creating database tables: {e}")
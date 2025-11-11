# services/engine_astra/database.py
import os
from sqlalchemy import create_engine, Column, String, Float, Integer, Date, UniqueConstraint
from sqlalchemy.orm import sessionmaker, declarative_base # Updated import

# Get the database URL from the environment variable
DATABASE_URL = os.environ.get('DATABASE_URL')

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base() # Updated function call

# --- Define Our Database Tables ---

class StockData(Base):
    """
    Table to store the daily OHLCV AND Technical Analysis data.
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
    
    # --- NEW COLUMNS FOR PHASE 3 ---
    rsi = Column(Float)
    macd = Column(Float)
    macd_signal = Column(Float)
    ema_50 = Column(Float)
    ema_200 = Column(Float)
    # --- END NEW COLUMNS ---
    
    __table_args__ = (UniqueConstraint('ticker', 'date', name='_ticker_date_uc'),)


class FundamentalData(Base):
    """
    Table to store fundamental data and our FINAL AI verdicts.
    This table will have ONE row per stock.
    """
    __tablename__ = "fundamental_data"
    
    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, unique=True, nullable=False)
    
    # --- NEW COLUMNS FOR PHASE 3 ---
    company_name = Column(String)
    sector = Column(String)
    industry = Column(String)
    market_cap = Column(Float)
    pe_ratio = Column(Float)
    eps = Column(Float)
    beta = Column(Float)
    # --- END NEW COLUMNS ---
    
    # --- FUTURE COLUMNS (for AI & Rules Engine) ---
    # sentiment_score = Column(Float)
    # short_term_signal = Column(String)
    # short_term_target = Column(Float)
    # ai_confidence = Column(Float)
    # ...etc
    

# --- Utility Function ---
def create_db_and_tables():
    """
    This function will be called by the worker to create the tables
    if they don't already exist.
    """
    try:
        # This command tells SQLAlchemy to find all tables that
        # inherit from 'Base' and create them in the database.
        # It will *add* the new columns without destroying existing data.
        Base.metadata.create_all(bind=engine)
        print("Database tables created/updated.")
    except Exception as e:
        print(f"Error creating database tables: {e}")
import os
import time
import math
import random
import pandas as pd
import yfinance as yf
from datetime import datetime
from celery import Celery
from sqlalchemy.dialects.postgresql import insert 
import numpy as np 

from shared.database import SessionLocal, create_db_and_tables, StockData, FundamentalData, SectorPerformance, CatalystEvent
from shared.stock_list import NIFTY50_TICKERS, MACRO_TICKERS
from technical_analysis import add_ta_features
from ai_models import train_prophet_model, train_classifier_model, train_ensemble_model, load_model, train_nbeats_model
from rules_engine import analyze_stock
# Phase 2.1: Market Regime
from market_regime import detect_market_regime
# Phase 4.1: Explainability
from explainability import explain_prediction
from tuning import optimize_ensemble_hyperparameters
import logging
import traceback

from shared.fundamental_analysis import compute_fundamental_ratios, calculate_piotroski_f_score, altman_z_score, beneish_m_score, get_fundamental_score, get_risk_score
from shared.news_analysis import analyze_news_sentiment
from shared.sector_analysis import update_sector_trends
from strategy_registry import StrategyRegistry # Phase 2.2

# Import the Chanakya Agent
try:
    from chanakya_agent import generate_chanakya_reasoning
except ImportError:
    # Fallback if file is missing during migration/build
    def generate_chanakya_reasoning(*args, **kwargs): return "Chanakya Agent not found."

try:
    from ai_catalyst import generate_ai_catalyst
except ImportError:
    def generate_ai_catalyst(*args): return 0, None

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
app = Celery('astra_tasks', broker=REDIS_URL, backend=REDIS_URL)
app.conf.task_default_queue = 'astra_q'

def fetch_ticker_data_with_retry(ticker, retries=3):
    """Robust fetcher to handle Yahoo Finance network errors."""
    for i in range(retries):
        try:
            t = yf.Ticker(ticker)
            _ = t.info 
            return t
        except Exception as e:
            if i == retries - 1:
                print(f"ASTRA: Failed to fetch {ticker} after {retries} attempts: {e}")
                return None
            time.sleep(2) # Wait 2s before retry
    return None

def fetch_macro_data():
    """Fetches macro indicators (Phase 1, Task 1.2). Returns dict of Series or DF."""
    # We implement a caching mechanism or just fetch fresh. 
    # Since this is run per task, we'll fetch fresh but handle errors gracefully.
    macro_dfs = []
    for name, ticker in MACRO_TICKERS.items():
        try:
            m_t = yf.Ticker(ticker)
            m_df = m_t.history(period="2y", interval="1d") # Matching process_one_stock period
            if not m_df.empty:
                m_close = m_df[['Close']].rename(columns={'Close': f'macro_{name.lower()}'})
                m_close.index = m_close.index.tz_localize(None)
                macro_dfs.append(m_close)
        except: 
            logging.error(f"Macro Fetch Error: {traceback.format_exc()}")
    return macro_dfs

def get_sector_status(db, sector_name):
    """
    Finds the sector status from DB using fuzzy matching.
    """
    if not sector_name or sector_name == "Unknown": return "NEUTRAL"
    
    # Try direct match first
    sec = db.query(SectorPerformance).filter(SectorPerformance.sector_name == sector_name).first()
    if sec: return sec.status
    
    # Try partial match (e.g., 'Financial Services' -> 'Financial')
    all_sectors = db.query(SectorPerformance).all()
    for s in all_sectors:
        if s.sector_name.lower() in sector_name.lower() or sector_name.lower() in s.sector_name.lower():
            return s.status
            
    return "NEUTRAL"

import logging
import traceback
from tuning import optimize_ensemble_hyperparameters

# ... existing code ...

@app.task(name="astra.train_models")
def train_stock_models(ticker):
    """
    HEAVY TASK: Trains Prophet, XGBoost, and Ensemble models.
    Should be run weekly or on-demand, NOT on every page load.
    """
    logging.info(f"ASTRA-TRAIN: Starting training for {ticker}...")
    try:
        t = fetch_ticker_data_with_retry(ticker)
        if not t: return f"Failed to fetch {ticker}"
        
        data = t.history(period="5y", interval="1d", auto_adjust=False) # Train on more data
        if data.empty: return f"No data for {ticker}"

        # MERGE MACRO DATA (Task 1.2)
        # We need 5y for training too
        macro_dfs = []
        for name, mt in MACRO_TICKERS.items():
            try:
                m_t = yf.Ticker(mt)
                m_df = m_t.history(period="5y", interval="1d")
                if not m_df.empty:
                    m_close = m_df[['Close']].rename(columns={'Close': f'macro_{name.lower()}'})
                    m_close.index = m_close.index.tz_localize(None)
                    macro_dfs.append(m_close)
            except: 
                logging.error(traceback.format_exc())
        
        data.index = data.index.tz_localize(None)
        data = data[~data.index.duplicated(keep='first')]
        if macro_dfs:
            for m in macro_dfs:
                data = data.join(m, how='left')
                data[m.columns[0]] = data[m.columns[0]].ffill()
        
        ai_df = add_ta_features(data).reset_index().rename(columns={'Date':'date','Close':'close','Volume':'volume','Open':'open','High':'high','Low':'low'})
        
        # Phase 3.3: Hyperparameter Optimization
        best_params = {}
        try:
            # Only run if we have enough data
            if len(ai_df) > 100:
                logging.info(f"ASTRA-TRAIN: Optimizing hyperparameters for {ticker}...")
                best_params = optimize_ensemble_hyperparameters(ai_df, ticker)
        except Exception as e:
             logging.error(f"Hyperopt Failed for {ticker}: {traceback.format_exc()}")

        # Train & Save (Functions now return metrics/data, not models)
        _ = train_prophet_model(ai_df, ticker)
        _ = train_nbeats_model(ai_df, ticker) # Phase 3.1: Darts
        conf = train_classifier_model(ai_df, ticker)
        rmse = train_ensemble_model(ai_df, ticker, horizon=1, best_params=best_params)
        
        logging.info(f"ASTRA-TRAIN: {ticker} Done. Conf={conf:.2f}, RMSE={rmse:.4f}")
        return f"Success: {ticker}"
        
    except Exception as e:
        logging.error(f"ASTRA-TRAIN: Error {ticker}: {traceback.format_exc()}")
        return f"Error: {e}"


# --------------------------------------------------------------------------
# Phase 2: Refactored Processing with Rate Limiting & DB Catalysts
# --------------------------------------------------------------------------

def get_catalyst_from_db(ticker):
    """
    Fetches active catalyst from Postgres (replaces catalyst_store.py).
    """
    db = SessionLocal()
    try:
        event = db.query(CatalystEvent).filter(
            CatalystEvent.ticker == ticker,
            CatalystEvent.is_active == True
        ).first()
        if event:
             return event.score, event.context
        return 0, None
    finally:
        db.close()

@app.task(name="astra.process_stock", rate_limit='12/m') # 12 per min = 1 request every 5s
def process_one_stock(ticker):
    """
    LIGHTWEIGHT TASK: Loads models, runs inference, and updates DB.
    Rate Limited to prevent Yahoo Finance IP bans.
    """
    print(f"ASTRA: Processing {ticker} (Inference Only)...")
    db = SessionLocal()
    try:
        t = fetch_ticker_data_with_retry(ticker)
        if not t: return False
        
        # 2. PRICE DATA
        data = t.history(period="2y", interval="1d", auto_adjust=False)
        if data.empty: return False
        
        # MERGE MACRO (Task 1.2) - Localized inline to be self-contained
        macro_dfs = fetch_macro_data()
        data.index = data.index.tz_localize(None)
        data = data[~data.index.duplicated(keep='first')]
        if macro_dfs:
            for m in macro_dfs:
                data = data.join(m, how='left')
                data[m.columns[0]] = data[m.columns[0]].ffill()

        data_with_ta = add_ta_features(data)
        
        # Save History
        stock_records = []
        for index, row in data_with_ta.iterrows():
            if pd.isna(row['Open']): continue
            rec = {
                "ticker": ticker, "date": index.date(),
                "open": float(row['Open']), "high": float(row['High']), "low": float(row['Low']), "close": float(row['Close']),
                "volume": int(row['Volume']), "rsi": float(row['rsi']), "macd": float(row['macd']), "macd_signal": float(row['macd_signal']),
                "ema_50": float(row['ema_50']), "ema_200": float(row['ema_200']), "atr": float(row.get('atr', 0.0))
            }
            # Note: We are NOT saving macro data to stock_data table yet as schema update isn't requested in Phase 1 tasks explicitly for DB.
            stock_records.append(rec)
        
        if stock_records:
            stmt = insert(StockData).values(stock_records)
            update_dict = { k: stmt.excluded[k] for k in ['open','high','low','close','volume','rsi','macd','macd_signal','ema_50','ema_200','atr']}
            stmt = stmt.on_conflict_do_update(index_elements=['ticker', 'date'], set_=update_dict)
            db.execute(stmt)

        # 3. FUNDAMENTALS
        fin = t.financials; bal = t.balance_sheet; cf = t.cashflow; info = t.info
        f_score = calculate_piotroski_f_score(t)
        z_score = altman_z_score(fin, bal, info.get('marketCap', 0))
        m_score = beneish_m_score(fin, bal, cf)
        funda_dict = compute_fundamental_ratios(t)
        
        # Calculate Scores
        comp_score = 0
        if f_score >= 7: comp_score += 30
        elif f_score >= 5: comp_score += 15
        if funda_dict['revenue_growth'] > 0.15: comp_score += 20
        pe = info.get('trailingPE', 0)
        if 0 < pe < 25: comp_score += 20
        latest_rsi = data_with_ta['rsi'].iloc[-1]
        if 40 <= latest_rsi <= 70: comp_score += 30

        funda_dict.update({'piotroski_f_score': f_score, 'altman_z_score': z_score, 'beneish_m_score': m_score})
        score_news = analyze_news_sentiment(ticker)

        # 4. AI INFERENCE (LOAD, DON'T TRAIN)
        ai_df = data_with_ta.reset_index().rename(columns={'Date':'date','Close':'close','Volume':'volume','Open':'open','High':'high','Low':'low'})
        
        # Load Models
        prophet_model = load_model(ticker, 'prophet')
        xgb_cls = load_model(ticker, 'xgb_cls')
        ensemble_model = load_model(ticker, 'ensemble')
        
        # Forecast
        forecast = None
        if prophet_model:
            try:
                future = prophet_model.make_future_dataframe(periods=300) # Re-use model for new dates
                forecast = prophet_model.predict(future)
            except Exception as e:
                print(f"ASTRA: Prophet Prediction Failed for {ticker}: {e}")
                forecast = None
            
        # Confidence
        confidence = 0.5 # Default
        features_cls = ['rsi', 'macd', 'ema_50', 'close', 'volume', 'atr', 'momentum_7', 'vol_spike']
        if xgb_cls:
             try:
                 last_row_cls = ai_df.iloc[[-1]][features_cls].fillna(0)
                 pred_cls = xgb_cls.predict(last_row_cls)[0]
                 confidence = 0.8 if pred_cls == 1 else 0.2
             except Exception as e:
                 print(f"ASTRA: XGBoost Prediction Failed for {ticker}: {e}")
                 confidence = 0.5
        
        # Ensemble Prediction
        predicted_return = 0.0
        features_ens = ['open','high','low','close','volume','rsi','macd','atr','ema_50','bb_u','bb_l','momentum_7','vol_spike','close_lag_1','close_lag_2','close_lag_3','close_lag_5']
        if ensemble_model:
            try:
                last_row_ens = ai_df.iloc[[-1]][features_ens].fillna(0)
                predicted_return = float(ensemble_model.predict(last_row_ens)[0])
                # Phase 4.1: Explain Prediction with SHAP
                shap_explanation = explain_prediction(ensemble_model, last_row_ens)
            except Exception as e:
                print(f"ASTRA: Ensemble Prediction Failed for {ticker}: {e}")
                predicted_return = 0.0
                shap_explanation = "Ensemble model failed."
        else:
            shap_explanation = "No model explanation available."

        current_close = float(ai_df['close'].iloc[-1])
        predicted_close = current_close * (1 + predicted_return)

        latest = data_with_ta.iloc[-1]
        atr_val = latest.get('atr', latest['Close']*0.02)
        
        # SECTOR CHECK
        sector_name = info.get('sector', 'Unknown')
        sector_status = get_sector_status(db, sector_name)

        # MARKET REGIME (Task 2.1)
        # We should calculate or fetch this. Ideally calculated globally once per day, 
        # but for now we call the function (it has its own fetch inside, slightly inefficient but correct).
        # Optimization: Cache this result or computation.
        market_regime = detect_market_regime()
        # market_regime is 1, -1, or 0.
        # We can add this to the AI Model features in "cross-sectional" step if we want,
        # but the prompt says to "merge into individual stock data".
        # For inference, the model was trained with whatever features it had.
        # If we re-train with market_regime, we need it here.
        # Current Ensemble Model features do NOT include 'market_regime' in the list yet.
        # But we should save it or use it for Rules Engine modification?
        # Task 2.1 says "Output: An integer feature market_regime... to be merged".
        # If we update ENSEMBLE_FEATURES, we need to pass it to the model.
        # For now, let's just log it or pass to analyze_stock if supported.
        # analyze_stock doesn't explicitly take market_regime yet, but we can pass it via 'sector_status' logic or new arg.
        
        # Let's adjust 'Sector Status' influence or just print it for now as part of the 'Context'.
        
        # STRATEGY REGISTRY (Phase 2.2)
        # 1. Look up strategy based on Regime
        strategy_engine = StrategyRegistry()
        active_strategy_func = strategy_engine.get_strategy(market_regime)
        strategy_signal = active_strategy_func(ai_df)
        print(f"ASTRA: Regime={market_regime} -> Strategy Signal={strategy_signal}")

        # CATALYST CHECK (DB + AI Fallback)
        cat_score, cat_context = get_catalyst_from_db(ticker)
        
        # If DB is empty, ask AI (Dynamic Generation)
        if cat_score == 0:
            print(f"ASTRA: No manual catalyst for {ticker}. Asking AI...")
            cat_score, cat_context = generate_ai_catalyst(ticker)
            
            # Save AI discovery to DB (Cache it)
            if cat_score > 0:
                try:
                    new_cat = CatalystEvent(ticker=ticker, score=cat_score, context=cat_context, is_active=True)
                    db.add(new_cat)
                    db.commit() # Commit immediately so it persists
                    print(f"ASTRA: AI Found & Saved Catalyst for {ticker}: {cat_score}")
                except Exception as e:
                    print(f"ASTRA: Failed to save AI catalyst: {e}")
                    db.rollback()

        # Pass DataFrame (ai_df) to analyze_stock
        analysis = analyze_stock(
            ticker, 
            ai_df,  # Passing full DF with TA features
            funda_dict, 
            float(score_news), 
            float(confidence), 
            forecast, # Prophet forecast
            sector=sector_name,
            sector_status=sector_status,
            catalyst_score=float(cat_score) 
        )
        
        # --- PHASE 3: AGENTIC REASONING ---
        summary = {
            'sector': sector_name,
            'sector_status': sector_status,
            'trend': analysis['st']['rr'], # Using RR or Trend from new analysis
            'quality': 'High' if f_score >= 7 else 'Low',
            'risk': analysis['risk_level'],
            'target': analysis['st']['target']
        }
        
        ai_narrative = generate_chanakya_reasoning(
            ticker, 
            analysis['st']['verdict'], 
            analysis['ai_confidence'],
            summary,
            catalyst_context=cat_context,
            shap_explanation=shap_explanation # Pass SHAP context
        )
        
        if "Chanakya is" in ai_narrative or "LLM Error" in ai_narrative:
             final_reasoning = analysis['reasoning'] + f"\n\n**Agent Note:** {ai_narrative}"
        else:
             final_reasoning = ai_narrative

        # 5. SAVE
        existing = db.query(FundamentalData).filter(FundamentalData.ticker == ticker).first()
        
        # Map Risk Level to Score (Low=20, Med=50, High=80)
        r_map = {"LOW": 20.0, "MEDIUM": 50.0, "HIGH": 80.0}
        risk_score_val = r_map.get(analysis['risk_level'], 50.0)

        data_dict = {
            "company_name": info.get('longName', ticker),
            "sector": sector_name, "industry": info.get('industry', 'Unknown'),
            "market_cap": float(info.get('marketCap', 0)), "pe_ratio": float(info.get('trailingPE', 0)),
            "eps": float(info.get('trailingEps', 0)), "beta": float(info.get('beta', 0)),
            "piotroski_f_score": int(f_score), "altman_z_score": float(z_score), "beneish_m_score": float(m_score),
            "score_fundamental": 50.0, "score_news": float(score_news),
            "score_risk": risk_score_val, # Saving Risk Score
            
            "st_verdict": analysis['st']['verdict'], "st_target": float(analysis['st']['target']), "st_stoploss": float(analysis['st']['sl']),
            "mt_verdict": analysis['mt']['verdict'], "mt_target": float(analysis['mt']['target']), "mt_stoploss": float(analysis['mt']['sl']),
            "lt_verdict": analysis['lt']['verdict'], "lt_target": float(analysis['lt']['target']), "lt_stoploss": float(analysis['lt']['sl']),
            
            "ai_reasoning": final_reasoning, 
            "ai_confidence": float(analysis['ai_confidence']), 
            "predicted_close": predicted_close, "ensemble_score": float(comp_score),
            "last_updated": datetime.now().date()
        }
        
        if existing:
            for k, v in data_dict.items(): setattr(existing, k, v)
        else:
            db.add(FundamentalData(ticker=ticker, **data_dict))
            
        db.commit()
        print(f"ASTRA: DONE {ticker}. Sector: {sector_status}")
        return True

    except Exception as e:
        db.rollback()
        logging.error(f"ASTRA: ERROR {ticker}: {traceback.format_exc()}")
        return False
    finally:
        db.close()


@app.task(name="astra.run_sector_update")
def run_sector_update():
    db = SessionLocal()
    update_sector_trends(db)
    db.close()
    return "Sector Update Complete"


@app.task(name="astra.run_nightly_update")
def run_nightly_update():
    """
    DISPATCHER: Only fires off the tasks.
    Rate limiting is handled by the worker queue configuration (12/m).
    """
    print("ASTRA: Dispatching Nightly Update Tasks...")
    
    # Fire and Forget - The Rate Limiter will handle the spacing
    for ticker in NIFTY50_TICKERS:
        process_one_stock.delay(ticker)
        
    print(f"ASTRA: Dispatched {len(NIFTY50_TICKERS)} tasks to queue.")
    return "Success"


@app.task(name="astra.run_single_stock_update")
def run_single_stock_update(ticker):
    print(f"ASTRA: Received on-demand request for {ticker}...")
    
    db = SessionLocal()
    try:
        update_sector_trends(db) # Context First
    except: 
        logging.error(f"Context Update Failed: {traceback.format_exc()}")
    finally: db.close()

    # Call directly (bypass rate limit for user request) or use .delay() to enforce it
    # Ideally for UX, we want it fast, so we call directly here, assuming user won't spam.
    return process_one_stock(ticker) # Direct call


@app.task(name="astra.run_backtest")
def run_backtest_task(ticker, start_date, end_date):
    """
    Runs a historical backtest for a single ticker.
    Returns JSON report.
    """
    from backtest_engine import BacktestEngine
    print(f"ASTRA-BACKTEST: Starting {ticker} ({start_date} to {end_date})")
    
    engine = BacktestEngine(ticker)
    results = engine.run(start_date, end_date)
    
    if results is None:
        return {"status": "failed", "reason": "No data or empty results"}
        
    # Phase 1 Update: results is now a DICT from VectorBT (Stats)
    
    return {
        "status": "success",
        "ticker": ticker,
        "total_days": "N/A", # VBT aggregates this
        "total_trades": results.get("Total Trades", 0),
        "win_rate": round(results.get("Win Rate [%]", 0), 2),
        "sharpe": round(results.get("Sharpe Ratio", 0), 2),
        "max_drawdown": round(results.get("Max Drawdown [%]", 0), 2),
        "data": results # Return the whole dict for valid consumption
    }

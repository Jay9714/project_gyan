import pandas as pd
import numpy as np
import os
import pickle
import joblib
import logging
import traceback
from prophet import Prophet
# Phase 3: Darts & Boosting
from darts import TimeSeries
from darts.models import NBEATSModel, TCNModel
from catboost import CatBoostClassifier, CatBoostRegressor, Pool
from lightgbm import LGBMRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, StackingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, mean_squared_error
from xgboost import XGBRegressor, XGBClassifier

# Directory to save models inside the container
MODEL_DIR = "/app/saved_models"
os.makedirs(MODEL_DIR, exist_ok=True)

# Define features used in the ensemble model (must match tasks.py)
# Phase 2: Added vol_rel, dist_ema, atr_pct
ENSEMBLE_FEATURES = ['open', 'high', 'low', 'close', 'volume', 'rsi', 'macd', 'atr', 'ema_50', 'bb_u', 'bb_l', 'momentum_7', 'vol_spike', 'close_lag_1', 'close_lag_2', 'close_lag_3', 'close_lag_5', 'vol_rel', 'dist_ema', 'atr_pct']

# Phase 3: Helper for Darts
def prepare_darts_series(df, relevant_cols=None):
    if relevant_cols is None:
        relevant_cols = ['close', 'volume', 'rsi']
    # Ensure datetime index
    if 'date' in df.columns:
        df = df.set_index('date')
    series = TimeSeries.from_dataframe(df, value_cols=relevant_cols, fill_missing_dates=True, freq='D')
    return series

# --- LOADING & INFERENCE ---

def load_model(ticker, model_type="prophet"):
    """
    Loads a saved model from disk.
    model_type: 'prophet', 'xgb_cls', 'ensemble'
    """
    try:
        filename = ""
        if model_type == "prophet": filename = f"{ticker}_prophet.pkl"
        elif model_type == "xgb_cls": filename = f"{ticker}_xgb_cls.pkl"
        elif model_type == "ensemble": filename = f"{ticker}_ensemble.pkl"
        
        path = os.path.join(MODEL_DIR, filename)
        if not os.path.exists(path):
            return None
            
        return joblib.load(path) if model_type != "prophet" else pickle.load(open(path, 'rb'))
        
    except Exception as e:
        logging.error(f"AI_LOAD_ERROR {ticker} {model_type}: {traceback.format_exc()}")
        return None

# --- TRAINING FUNCTIONS (Decoupled) ---

def train_prophet_model(df, ticker):
    """
    Trains and SAVES Prophet model. Returns Forecast + Metrics (No Model Object).
    """
    # Prepare data for Prophet (ds = date, y = close)
    df_prophet = df[['date', 'close']].rename(columns={'date': 'ds', 'close': 'y'})
    
    # Ensure date is timezone-naive
    if pd.api.types.is_datetime64_any_dtype(df_prophet['ds']):
         df_prophet['ds'] = df_prophet['ds'].dt.tz_localize(None)
    
    # --- TUNING FOR ACCURACY ---
    model = Prophet(
        daily_seasonality=True,
        changepoint_prior_scale=0.5, 
        seasonality_mode='multiplicative'
    )
    
    try:
        model.add_country_holidays(country_name='IN')
    except:
        pass 
        
    model.fit(df_prophet)
    
    # Save Model
    model_path = os.path.join(MODEL_DIR, f"{ticker}_prophet.pkl")
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
        
    # Create Forecast (1 Year into future)
    future = model.make_future_dataframe(periods=365)
    forecast = model.predict(future)
    
    return forecast # Return only data, not the heavy model object

# Phase 3.1: Darts Implementation
def train_nbeats_model(df, ticker):
    """
    Trains N-BEATS model using Darts.
    Returns: Forecast Series (values)
    """
    try:
        # Prepare Data
        # We need continuous time series
        series = prepare_darts_series(df, ['close', 'rsi', 'volume'])
        
        # Split
        train, val = series.split_before(0.9)
        
        # Model
        # N-BEATS is deep learning, so it might be slow on CPU. 
        # Using simplified parameters for "Free Tools" constraint (assuming no GPU or limited CPU)
        model = NBEATSModel(
            input_chunk_length=30,
            output_chunk_length=7,
            n_epochs=20, # Reduced from 100 for speed
            random_state=42,
            force_reset=True,
            save_checkpoints=True,
            model_name=f"{ticker}_nbeats",
            work_dir=MODEL_DIR
        )
        
        model.fit(train, val_series=val, verbose=False)
        
        # Forecast 10 days
        pred = model.predict(n=10)
        
        # Save? Darts saves checkpoints automatically if configured, 
        # but we can pickle the wrapper if needed. 
        # For now, we return predictions.
        return pred.values()
        
    except Exception as e:
        print(f"DARTS_ERROR {ticker}: {e}")
        return None


def train_classifier_model(df, ticker):
    """
    Trains and SAVES XGBoost Classifier. Returns Confidence Score.
    """
    data = df.copy()
    
    # Create Target: 1 if Close price tomorrow > Close price today
    data['Target'] = (data['close'].shift(-1) > data['close']).astype(int)
    
    # Features for classification
    features = ['rsi', 'macd', 'ema_50', 'close', 'volume', 'atr', 'momentum_7', 'vol_spike']
    # Ensure features exist
    for f in features: 
        if f not in data.columns: data[f] = 0
            
    data = data.dropna()
    
    if len(data) < 50:
        return 0.0 
    
    X = data[features]
    y = data['Target']
    
    # Split Data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)
    
    # Handle Class Imbalance
    ratio = float(np.sum(y_train == 0)) / np.sum(y_train == 1) if np.sum(y_train == 1) > 0 else 1.0
    
    # Train XGBoost Classifier
    model = XGBClassifier(
        n_estimators=200, 
        learning_rate=0.05, 
        max_depth=5, 
        scale_pos_weight=ratio, 
        n_jobs=1,              # Fixed: n_jobs=1 to avoid Celery/Loky conflict
        use_label_encoder=False, 
        eval_metric='logloss'
    )
    model.fit(X_train, y_train)
    
    # Calculate Confidence
    preds = model.predict(X_test)
    confidence = precision_score(y_test, preds, zero_division=0)
    
    # Save Model
    model_path = os.path.join(MODEL_DIR, f"{ticker}_xgb_cls.pkl")
    joblib.dump(model, model_path)
    
    # Phase 3.2: Train CatBoost Classifier as well (and blend or save separate)
    # For now, we keep XGB as primary Classifier to not break `tasks.py`, 
    # but we can add CatBoost to the Ensemble Regressor below.
        
    return confidence



def train_ensemble_model(df, ticker, horizon=1, best_params=None):
    """
    Trains and SAVES Ensemble Model. Returns RMSE.
    Accepts best_params dict for XGBoost tuning.
    """
    data = df.copy()
    
    # --- Predict Returns, not Price ---
    data['Target'] = np.log(data['close'].shift(-horizon) / data['close'])
    
    features_to_use = [f for f in ENSEMBLE_FEATURES + ['vol_rel', 'dist_ema', 'atr_pct'] if f in data.columns]
    data = data.dropna()
    
    if len(data) < 50:
        return 0.0 

    X = data[features_to_use].fillna(0)
    y = data['Target']
    
    # Split Data
    split_index = int(len(data) * 0.8)
    X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]
    
    # XGB Params
    xgb_params = {
        'n_estimators': 100, 
        'learning_rate': 0.03, 
        'max_depth': 6, 
        'subsample': 0.8, 
        'colsample_bytree': 0.8,
        'enable_categorical': True, 
        'verbosity': 0, 
        'n_jobs': 1 
    }
    
    if best_params:
        xgb_params.update(best_params)

    # 3. Define Base Estimators
    estimators = [
        ('rf', RandomForestRegressor(
            n_estimators=100,
            max_depth=10, 
            min_samples_split=5, 
            random_state=42, 
            n_jobs=1 
        )), 
        ('xgb', XGBRegressor(**xgb_params)),
        ('cat', CatBoostRegressor(
            iterations=100, 
            learning_rate=0.03, 
            depth=6, 
            verbose=False,
            allow_writing_files=False 
        )),
        ('lgbm', LGBMRegressor(
            n_estimators=100,
            learning_rate=0.05,
            n_jobs=1,
            verbose=-1
        ))
    ]

    # 4. Train Stacking Regressor
    model = StackingRegressor(estimators=estimators, final_estimator=LinearRegression(), n_jobs=1)
    model.fit(X_train, y_train)
    
    # 5. Evaluate
    preds = model.predict(X_test)
    
    mse = mean_squared_error(y_test, preds)
    rmse = np.sqrt(mse)
    
    # 6. Save Model
    model_path = os.path.join(MODEL_DIR, f"{ticker}_ensemble.pkl")
    joblib.dump(model, model_path)
        
    return rmse
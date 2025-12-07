import pandas as pd
import numpy as np
import os
import pickle
import joblib
from prophet import Prophet
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, StackingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, mean_squared_error
from xgboost import XGBRegressor, XGBClassifier

# Directory to save models inside the container
MODEL_DIR = "/app/saved_models"
os.makedirs(MODEL_DIR, exist_ok=True)

# Define features used in the ensemble model (must match tasks.py)
ENSEMBLE_FEATURES = ['open', 'high', 'low', 'close', 'volume', 'rsi', 'macd', 'atr', 'ema_50', 'bb_u', 'bb_l', 'momentum_7', 'vol_spike', 'close_lag_1', 'close_lag_2', 'close_lag_3', 'close_lag_5']

def train_prophet_model(df, ticker):
    """
    Trains a Prophet model to predict the closing price.
    Tuned for 'Turnaround' stocks (high sensitivity to recent trends).
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
    
    return model, forecast

def train_classifier_model(df, ticker):
    """
    Trains an XGBoost Classifier to predict 'Buy' (1) or 'Sell' (0).
    Target: Does price go up tomorrow?
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
        return None, 0.0 
    
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
        n_jobs=-1, 
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
        
    return model, confidence

def train_ensemble_model(df, ticker, horizon=1):
    """
    Trains a Stacking Regressor (Ensemble) to predict future price.
    Target: Close price shifted forward by 'horizon' days.
    """
    data = df.copy()
    
    # 1. Create Target (Price prediction 'horizon' days ahead)
    data['Target'] = data['close'].shift(-horizon)
    
    # 2. Prepare Data
    features = [f for f in ENSEMBLE_FEATURES if f in data.columns]
    data = data.dropna()
    
    if len(data) < 50:
        return None, 0.0 

    X = data[features].fillna(0)
    y = data['Target']
    
    # Split Data
    split_index = int(len(data) * 0.8)
    X_train, X_test = X.iloc[:split_index], X.iloc[split_index:]
    y_train, y_test = y.iloc[:split_index], y.iloc[split_index:]
    
    # 3. Define Base Estimators (Must use Regressors)
    estimators = [
        ('rf', RandomForestRegressor(n_estimators=50, random_state=42, n_jobs=-1)), 
        ('xgb', XGBRegressor(n_estimators=50, random_state=42, enable_categorical=True, verbosity=0, n_jobs=-1)) 
    ]

    # 4. Train Stacking Regressor
    model = StackingRegressor(estimators=estimators, final_estimator=LinearRegression(), n_jobs=-1)
    model.fit(X_train, y_train)
    
    # 5. Evaluate
    preds = model.predict(X_test)
    
    # --- UNIVERSAL FIX: Calculate RMSE Manually ---
    # This works on ALL scikit-learn versions (old and new)
    mse = mean_squared_error(y_test, preds)
    rmse = np.sqrt(mse)
    # ----------------------------------------------
    
    # 6. Save Model
    model_path = os.path.join(MODEL_DIR, f"{ticker}_ensemble.pkl")
    joblib.dump(model, model_path)
        
    return model, rmse
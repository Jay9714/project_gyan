import pandas as pd
import numpy as np
import os
import pickle
from prophet import Prophet
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score

# Directory to save models inside the container
MODEL_DIR = "/app/saved_models"
os.makedirs(MODEL_DIR, exist_ok=True)

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
    # changepoint_prior_scale=0.5: Allows model to react fast to recent trend changes (e.g. RBI news)
    # seasonality_mode='multiplicative': Handles high volatility stocks better
    model = Prophet(
        daily_seasonality=True,
        changepoint_prior_scale=0.5, 
        seasonality_mode='multiplicative'
    )
    
    try:
        # Try to add holidays, skip if library has issues or offline
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
    UPGRADE: Uses Gradient Boosting instead of Random Forest for higher accuracy.
    """
    data = df.copy()
    
    # Create Target: 1 if Close price tomorrow > Close price today
    data['Target'] = (data['close'].shift(-1) > data['close']).astype(int)
    
    # Select Features (These must match columns in tasks.py)
    features = ['rsi', 'macd', 'ema_50', 'close', 'volume', 'atr']
    
    # Drop rows with NaN (from TA calcs)
    data = data.dropna()
    
    if len(data) < 50:
        # Not enough data to train reliably
        return None, 0.0 
    
    X = data[features]
    y = data['Target']
    
    # Split Data (No shuffle, because it's time series data)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)
    
    # --- UPGRADE: XGBoost Implementation ---
    # scale_pos_weight: Helps if "Buy" signals are rare
    ratio = float(np.sum(y_train == 0)) / np.sum(y_train == 1) if np.sum(y_train == 1) > 0 else 1.0
    
    model = XGBClassifier(
        n_estimators=200,          # More trees than RF
        learning_rate=0.05,        # Slower learning for better generalization
        max_depth=5,               # Prevent overfitting
        subsample=0.8,             # Use 80% of data per tree
        colsample_bytree=0.8,      # Use 80% of features per tree
        scale_pos_weight=ratio,    # Handle class imbalance
        eval_metric='logloss',
        use_label_encoder=False,
        random_state=42,
        n_jobs=-1                  # Use all CPU cores (FASTER)
    )
    
    model.fit(X_train, y_train)
    
    # Calculate Confidence (Precision Score)
    preds = model.predict(X_test)
    
    # Precision: When model predicts UP, how often is it right?
    confidence = precision_score(y_test, preds, zero_division=0)
    
    # Save Model
    model_path = os.path.join(MODEL_DIR, f"{ticker}_xgb.pkl")
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
        
    return model, confidence
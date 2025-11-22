import pandas as pd
import numpy as np
import os
import pickle
from prophet import Prophet
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score

# Directory to save models inside the container
MODEL_DIR = "/app/saved_models"
os.makedirs(MODEL_DIR, exist_ok=True)

def train_prophet_model(df, ticker):
    """
    Trains a Prophet model to predict the closing price.
    Returns the model object and the 30-day forecast DataFrame.
    """
    # Prepare data for Prophet (ds = date, y = close)
    # Ensure date is timezone-naive to prevent Prophet errors
    df_prophet = df[['date', 'close']].rename(columns={'date': 'ds', 'close': 'y'})
    # Remove timezone info if present
    if pd.api.types.is_datetime64_any_dtype(df_prophet['ds']):
         df_prophet['ds'] = df_prophet['ds'].dt.tz_localize(None)
    
    # Train Model
    model = Prophet(daily_seasonality=True)
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
        
    # Create Forecast (30 days future)
    future = model.make_future_dataframe(periods=30)
    forecast = model.predict(future)
    
    return model, forecast

def train_classifier_model(df, ticker):
    """
    Trains a Random Forest Classifier to predict 'Buy' (1) or 'Sell' (0).
    Target: Does price go up tomorrow?
    Features: RSI, MACD, EMA_50, Close
    """
    data = df.copy()
    
    # Create Target: 1 if Close price tomorrow > Close price today
    data['Target'] = (data['close'].shift(-1) > data['close']).astype(int)
    
    # Select Features (These must match columns in tasks.py)
    features = ['rsi', 'macd', 'ema_50', 'close', 'volume']
    
    # Drop rows with NaN (from TA calcs)
    data = data.dropna()
    
    if len(data) < 50:
        # Not enough data to train reliably
        return None, 0.0 
    
    X = data[features]
    y = data['Target']
    
    # Split Data (No shuffle, because it's time series data)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, shuffle=False)
    
    # Train Random Forest
    model = RandomForestClassifier(n_estimators=100, min_samples_split=10, random_state=1)
    model.fit(X_train, y_train)
    
    # Calculate Confidence (Precision Score)
    preds = model.predict(X_test)
    # Precision: When model predicts UP, how often is it right?
    confidence = precision_score(y_test, preds, zero_division=0)
    
    # Save Model
    model_path = os.path.join(MODEL_DIR, f"{ticker}_rf.pkl")
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
        
    return model, confidence
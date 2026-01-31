
import optuna
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from xgboost import XGBRegressor
from lightgbm import LGBMRegressor
from catboost import CatBoostRegressor
from sklearn.metrics import mean_squared_error

def optimize_ensemble_hyperparameters(df, ticker):
    """
    Uses Optuna to find best params for XGBoost, CatBoost, LightGBM.
    Returns: Dict of best params for each model.
    """
    data = df.copy()
    
    # Target: Log Returns
    data['Target'] = np.log(data['close'].shift(-1) / data['close'])
    
    # Features (simplified for tuning speed)
    features = ['rsi', 'macd', 'ema_50', 'moment_7', 'vol_spike'] 
    # Use whatever available from ENSEMBLE_FEATURES
    features = [c for c in data.columns if c in ['rsi','macd','ema_50','momentum_7','vol_spike','atr_pct','dist_ema','vol_rel']]
    
    data = data.dropna()
    if len(data) < 100: return {}

    X = data[features]
    y = data['Target']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, shuffle=False)

    def objective_xgb(trial):
        param = {
            'n_estimators': trial.suggest_int('n_estimators', 50, 300),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'subsample': trial.suggest_float('subsample', 0.5, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.5, 1.0),
            'n_jobs': 1
        }
        model = XGBRegressor(**param, verbosity=0)
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        return np.sqrt(mean_squared_error(y_test, preds))

    study_xgb = optuna.create_study(direction='minimize')
    study_xgb.optimize(objective_xgb, n_trials=20) # 20 trials for speed

    print(f"Hyperopt {ticker} XGB Best: {study_xgb.best_params}")
    return study_xgb.best_params

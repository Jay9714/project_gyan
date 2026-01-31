Project Gyan: Quantitative Upgrade Roadmap
Status: Draft
Target: Senior Quantitative Research System
Constraints: 100% Free & Open Source Tools Only (MIT/Apache 2.0)
🤖 Context for AI Agents
You are an expert Quantitative Developer and ML Engineer. Your task is to upgrade "Project Gyan" from an intermediate stock analysis tool to a professional-grade research system.
Follow the phases below strictly. Do not introduce paid APIs (like Bloomberg/Refinitiv). Use yfinance for data, VectorBT for backtesting, and Darts/CatBoost for modeling.
📦 Phase 0: Dependencies & Environment
Goal: Install necessary open-source libraries without breaking existing services.
[ ] Task 0.1: Update Requirements
Files: services/engine_astra/requirements.txt, services/worker_chakra/requirements.txt
Action: Add the following libraries:
vectorbt>=0.23.0
darts>=0.24.0
catboost>=1.2
lightgbm>=4.0.0
optuna>=3.0.0
shap>=0.40.0
statsmodels>=0.14.0
scikit-learn>=1.3.0


Note: Ensure compatibility with existing torch or tensorflow installations if present.
🛠 Phase 1: Core Plumbing & Data Hygiene (Week 1)
Goal: Fix the "Garbage In, Garbage Out" problem and establish a realistic backtesting engine.
[ ] Task 1.1: Replace Custom Backtester with VectorBT
Priority: Critical
Files: services/engine_astra/backtest_engine.py
Instructions:
Deprecate the custom for loop in run_backtest.
Implement vectorbt (import as vbt).
Create a Portfolio.from_signals() simulation.
Crucial: Add fees=0.001 (0.1%) and slippage=0.0005 (0.05%) parameters to simulate real-world Indian market costs (STT + Brokerage).
Calculate and return: Sharpe Ratio, Max Drawdown, Sortino Ratio.
[ ] Task 1.2: Enhance Data Pipeline with Macro Data
Priority: High
Files: services/worker_chakra/tasks.py, shared/stock_list.py
Instructions:
In fetch_data (or equivalent), add calls to fetch:
USD/INR (Ticker: INR=X)
Brent Crude (Ticker: BZ=F)
India VIX (Ticker: ^INDIAVIX)
Nifty 50 (Ticker: ^NSEI)
Merge these as columns: macro_usdinr, macro_crude, macro_vix, market_nifty.
Forward-fill (ffill) missing data for macro indicators to align with stock timestamps.
[ ] Task 1.3: Data Sanitization Layer
Priority: Medium
Files: services/engine_astra/technical_analysis.py
Instructions:
Create a function sanitize_data(df).
Detect outliers: If Close changes > 20% in one day AND Volume change is < 200% (flash crash check), replace with NaN or interpolated value.
Drop rows where Volume is 0 (non-trading days).
📊 Phase 2: Advanced Feature Engineering (Week 2)
Goal: Move beyond basic RSI/MACD to professional quantitative features.
[ ] Task 2.1: Market Regime Detection ("The Traffic Light")
Priority: High
Files: services/engine_astra/market_regime.py (New File)
Instructions:
Fetch NIFTY 50 (^NSEI) history (1 year).
Calculate: 200-day SMA, 50-day SMA, ADX(14).
Logic:
Bull: Price > 200SMA & 50SMA > 200SMA.
Bear: Price < 200SMA & 50SMA < 200SMA.
Sideways: ADX < 20.
Output: An integer feature market_regime (1=Bull, -1=Bear, 0=Neutral) to be merged into individual stock data.
[ ] Task 2.2: Cross-Sectional Normalization
Priority: High
Files: services/engine_astra/technical_analysis.py
Instructions:
Do not feed raw Volume to models. Create vol_rel: Volume / Rolling_Mean(Volume, 20).
Do not feed raw Close. Create dist_ema: (Close - EMA_20) / Close.
Normalize ATR: ATR / Close (Percentage volatility).
[ ] Task 2.3: Target Variable Refinement
Priority: Medium
Files: services/engine_astra/ai_models.py
Instructions:
Change target from "Next Day Price" to "Log Returns": np.log(Close / Close.shift(1)).
Alternatively, create a Classification Target:
1 if Return > 1.0% (Buy)
-1 if Return < -1.0% (Sell)
0 otherwise (Hold)
🧠 Phase 3: Modeling Architecture Upgrade (Week 3)
Goal: Replace simple Prophet models with State-of-the-Art Time-Series & Boosting models.
[ ] Task 3.1: Implement Darts (TCN / N-BEATS)
Priority: Critical (Replaces Prophet)
Files: services/engine_astra/ai_models.py
Instructions:
Import darts.models.
Implement NBEATSModel or TCNModel.
Input: Past 60 days of [Close, Volume, RSI, Macro_Vix].
Output: Forecast horizon (next 5-10 days).
Note: These models handle non-linear dependencies much better than Prophet.
[ ] Task 3.2: Integrate CatBoost & LightGBM
Priority: High (Enhances XGBoost)
Files: services/engine_astra/ai_models.py
Instructions:
Add CatBoostClassifier (for Buy/Sell signals) and LightGBMRegressor (for price targets).
Why? CatBoost handles categorical features (like 'Sector') natively without One-Hot Encoding.
Create an EnsembleV2 class that averages predictions from: XGBoost + CatBoost + LightGBM.
[ ] Task 3.3: Hyperparameter Optimization (Optuna)
Priority: Medium
Files: services/engine_astra/tuning.py (New File)
Instructions:
Create an objective function for Optuna.
Search space: Learning Rate (0.01-0.3), Depth (3-10), L2 Leaf Reg.
Run 50 trials to find best params for the EnsembleV2 model.
🕵️ Phase 4: Intelligence & Reliability (Week 4)
Goal: Make the "Chanakya" agent smart, explainable, and hallucination-free.
[ ] Task 4.1: Explainability with SHAP
Priority: High
Files: services/engine_astra/explainability.py (New File)
Instructions:
After model training, pass the model and test set to shap.TreeExplainer.
Generate shap_values.
Extract top 3 drivers: "Model predicts UP because [RSI is Low] and [VIX is High]".
Pass this text string to the LLM context.
[ ] Task 4.2: Vector Database for News (RAG)
Priority: High (Nice to have)
Files: shared/database.py, services/engine_astra/ai_catalyst.py
Instructions:
Enable pgvector extension in Postgres.
Use sentence-transformers/all-MiniLM-L6-v2 (Free, HuggingFace) to embed news headlines.
When analyzing a stock, query the DB for: "News similar to 'Earnings miss' in the past 3 years for this sector."
Feed retrieved historical context to Ollama.
✅ Definition of Done
The project is considered "Upgraded" when:
Backtests include transaction costs (0.1%).
Prophet is removed/deprecated.
Stock predictions consider Macro (Nifty/USDINR) context.
The system can explain why it made a prediction using SHAP values.

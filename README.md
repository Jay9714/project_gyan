# 🏛️ Project Gyan: The "Chanakya" Quantitative Research System

> **"Astra" Release (v2.0)** - *Enterprise-Grade AI/ML Stock Analysis Platform*

**Project Gyan** is a state-of-the-art, open-source quantitative research ecosystem designed to democratize high-frequency-grade analytics. It combines **Agentic AI**, **Ensemble Machine Learning**, and **Vectorized Backtesting** into a microservices-based architecture to provide institutional-quality financial insights for the Indian Markets (NSE/BSE).

---

## 📚 Table of Contents
1. [System Architecture & Microservices](#-system-architecture--microservices)
2. [Technology Stack](#-technology-stack-deep-dive)
3. [Core Functionalities (The "Brain")](#-core-functionalities-embedded-intelligence)
   - [Phase 1: Data Engineering & VectorBT](#1-data-engineering--vectorized-backtesting)
   - [Phase 2: Market Regime & Signal Processing](#2-market-regime--signal-fidelity)
   - [Phase 3: Ensemble AI & Hyperparameter Tuning](#3-ensemble-ai--optuna-tuning)
   - [Phase 4: Agentic Reasoning (Chanakya)](#4-agentic-reasoning-chanakya-agent)
4. [Detailed Workflows](#-detailed-system-workflows)
5. [Installation & Setup](#-installation--setup)
6. [API Reference](#-api-reference)
7. [Developer Guide](#-developer-guide)

---

## 🏗 System Architecture & Microservices

Project Gyan follows a **Event-Driven Microservices Architecture**, containerized via Docker.

| Service Name | Container ID | Role | Port | Description |
| :--- | :--- | :--- | :--- | :--- |
| **Setu API** | `gyan_setu_api` | **Gateway** | `8000` | The central nervous system. A high-performance **FastAPI** (Async) layer that handles all incoming requests, serves data to the UI, and dispatches heavy compute tasks to the worker queue. Implements Polling patterns for long-running jobs. |
| **Astra Brain** | `gyan_astra_brain` | **Compute Engine** | - | The "Brain". A heavy **Celery** worker responsible for training ML models, running inference, executing VectorBT backtests, and calculating SHAP values. Scalable horizontally. |
| **Chakra Scheduler** | `gyan_chakra_scheduler` | **Cron Manager** | - | A specialized **Celery Beat** instance that orchestrates periodic tasks: Nightly Setup, Sector Updates, and Data Refresh jobs to ensure the DB never goes stale. |
| **Darpan UI** | `gyan_darpan_ui` | **Frontend** | `8501` | A simplified "Bloomberg Terminal" built with **Streamlit**. Visualizes complex data, renders interactive Plotly charts, and displays Agentic narratives. |

| **Ollama** | `gyan_ollama` | **LLM Server** | `11434` | Local inference server for Open-Source LLMs (Llama 3, Mistral). Ensures data privacy by keeping financial reasoning on-premise. |
| **PostgreSQL** | `gyan_db` | **Database** | `5432` | Relational automated storage for Fundamental Data, Stock Prices (1M+ rows), and User Configs. |
| **Redis** | `gyan_redis` | **Message Queue** | `6379` | High-speed message broker for Celery and result caching backend. |

---

## 🛠 Technology Stack (Deep Dive)

We use a curated stack of "Best-in-Class" open-source tools:

### Data & Simulation
*   **VectorBT (Pro-Grade Backtesting)**: Used for high-speed, vectorized simulation. We do not use simple `for` loops.
    *   *Implementation*: Simulates thousands of days in milliseconds.
    *   *Realism*: Configured with `fees=0.1%` (STT + Brokerage) and `slippage=0.05%` to prevent unrealistic profit expectations.
*   **YFinance**: Primary data source for OHLCV data. Wrapped with a robust retry mechanism and exponential backoff to handle rate limits.

### Machine Learning (The "Ensemble")
*   **XGBoost (Extreme Gradient Boosting)**: Optimized for speed and performance on structured tabular data.
*   **CatBoost (Categorical Boosting)**: Handles non-numerical features (like Sector, Industry) natively.
*   **LightGBM**: Microsoft's gradient boosting framework, used for its efficiency on large datasets.
*   **Darts (Time Series)**: A unified library for forecasting. We specifically implement the **N-BEATS** (Neural Basis Expansion Analysis) deep learning model for pure time-series forecasting.
*   **Prophet (Meta)**: Used for detecting seasonality and long-term trend components (Holt-Winters equivalent).
*   **Scikit-Learn**: The glue (StackingRegressor) that combines all above models into a single meta-prediction.

### Optimization & Explainability
*   **Optuna (Hyperparameter Tuning)**: An automated optimization framework that uses Bayesian optimization (TPE) to find the perfect learning rates and tree depths for our models dynamically.
*   **SHAP (Shapley Additive Explanations)**: Game-theoretic approach to explain *why* a model made a prediction. It breaks down a forecast into exact feature contributions (e.g., "RSI contributed +2% to likelihood").

---

## 🧠 Core Functionalities (Embedded Intelligence)

### 1. Data Engineering & Vectorized Backtesting
Unlike basic screeners, Project Gyan enforces strict data hygiene:
*   **Flash Crash Detection**: The `sanitize_data()` module scans for >20% price drops with low volume (bad ticks) and interpolates them.
*   **Macro Integration**: It doesn't look at stocks in isolation. It merges external signals:
    *   `USD/INR` (Currency strength)
    *   `Brent Crude` (Energy costs)
    *   `India VIX` (Risk sentiment)
*   These are fed as exogenous variables to all models.

### 2. Market Regime & Signal Processing
A naive model buys in a crash. Gyan uses a **Traffic Light System**:
*   **Logic**: Monitoring Nifty 50 relative to 200-SMA and ADX (Trend Strength).
    *   🟢 **Bull**: Price > 200SMA & ADX > 25
    *   🔴 **Bear**: Price < 200SMA
    *   🟡 **Sideways**: ADX < 20
*   This "Regime" signal is injected into the "Chanakya" Agent to suppress Buy signals during Bear markets.

### 3. Ensemble AI & Optuna Tuning
We don't rely on one model. We use a **Voting/Stacking Ensemble**:
1.  **Tier 1**: XGBoost, CatBoost, LightGBM, RandomForest, Prophet, N-BEATS generate individual predictions.
2.  **Tier 2 (Meta-Learner)**: A Linear Regressor learns which model is performing best *right now* and assigns weights dynamically.
3.  **Self-Correction**: The `optimize_ensemble_hyperparameters` task runs periodically using Optuna to retune the XGBoost parameters (Depth, Learning Rate) as market volatility shifts.

### 4. Agentic Reasoning ("Chanakya" Agent)
Raw numbers are hard to read. **Chanakya** is an LLM-wrapper that:
1.  Ingests the Numerical Analysis (RSI=30, Pred=Up).
2.  Ingests the SHAP Explanation ("Volume Spike drove this").
3.  Ingests Fundamental Data (PE Ratio, Piotroski Score).
4.  **Synthesizes a Narrative**: "While the technicals are oversold (RSI 30), the fundamentals are weak (F-Score 3). The model sees a bounce due to volume, but caution is advised due to the Bearish Market Regime."

---

## 🔄 Detailed System Workflows

### The "Ingest" Flow
1.  **Scheduler** triggers `run_nightly_update`.
2.  **Worker** fetches 2 years of OHLCV + Macro Data.
3.  **Sanitizer** cleans outliers.
4.  **FeatureStore** calculates 20+ Technical Indicators (RSI, MACD, Bollinger, Lags, Volatility).
5.  **DB**: Clean data is upserted into PostgreSQL.

### The "Think" Flow (Training)
1.  **Trigger**: User requests "Train" or automated weekly schedule.
2.  **Tuner**: Optuna runs 20 trials to find best `max_depth` and `learning_rate`.
3.  **Trainer**:
    *   Trains Prophet (Seasonality).
    *   Trains N-BEATS (Deep Learning).
    *   Trains XGB/Cat/LGBM (Gradient Boosting).
4.  **Ensembler**: stacks them and saves `.pkl` artifacts to `/saved_models`.

### The "Decide" Flow (Inference)
1.  **Loader**: Loads saved models from disk.
2.  **Predict**: Generates $T+1$ Return prediction.
3.  **Explain**: SHAP KernelExplainer generates feature importance.
4.  **Review**: Chanakya Agent drafts the verdict text.
5.  **Serve**: Results pushed to Postgres and Redis.

---

## 🚀 Installation & Setup

### Prerequisites
*   Docker Desktop (Windows/Mac/Linux)
*   16GB RAM Recommended (for LLM/ML usage)

### Step-by-Step
1.  **Clone**
    ```bash
    git clone https://github.com/project-gyan/core.git
    cd project_gyan
    ```

2.  **Environment Config**
    Create `.env` file:
    ```env
    POSTGRES_USER=postgres
    POSTGRES_PASSWORD=admin
    POSTGRES_DB=gyan_db
    REDIS_URL=redis://redis:6379/0
    ```

3.  **Launch**
    ```bash
    docker-compose up -d --build
    ```

4.  **Verify**
    *   UI: `http://localhost:8501`
    *   API: `http://localhost:8000/docs`

---

## 🔌 API Reference

### Backtesting
*   `GET /backtest/{ticker}`
    *   **Async**: Returns `{"task_id": "..."}` immediately.
    *   **Logic**: Triggers the `BacktestEngine` with VectorBT.
*   `GET /backtest/status/{task_id}`
    *   **Polling**: Returns `pending` or the full JSON result (Sharpe, Drawdown, Win Rate).

### Analysis
*   `GET /analysis/{ticker}`
    *   **Flow**: Checks DB -> If Stale, Triggers Background Update -> Returns cached data instantly.
*   `GET /screener/{horizon}`
    *   **Horizons**: `short` (14d), `mid` (60d), `long` (1y).
    *   **Filters**: High Quality (Piotroski > 5) for Long term.

---

## 💻 Developer Guide

### Directory Structure
```
project_gyan/
├── services/
│   ├── api_setu/          # FastAPI (The Gateway)
│   │   ├── main.py        # Endpoints
│   │   └── schemas.py     # Pydantic Models for Validation
│   ├── engine_astra/      # The AI Core
│   │   ├── ai_models.py   # Training/Inference Logic (XGB, Darts, Ensemble)
│   │   ├── backtest_engine.py # VectorBT Implementation
│   │   ├── market_regime.py   # Nifty Traffic Light Logic
│   │   ├── tasks.py       # Celery Task Definitions
│   │   ├── tuning.py      # Optuna Optimization
│   │   └── technical_analysis.py # TA-Lib wrappers & Sanitization
│   ├── frontend_darpan/   # Streamlit UI
│   └── worker_chakra/     # Celery Beat Config
├── shared/                # Shared Code (DB Models, Utils)
├── saved_models/          # Binary .pkl files (gitignored)
├── docker-compose.yml     # Orchestration
└── requirements.txt       # Dependencies
```

### Adding a New Model
1.  Open `ai_models.py`.
2.  Define `train_new_model(df, ticker)`.
3.  Add it to the `estimators` list in `train_ensemble_model`.
4.  The StackingRegressor will automatically learn to use it if it's good!

---
*Built with ❤️ by the Project Gyan Open Source Team.*

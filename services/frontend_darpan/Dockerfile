FROM python:3.11-slim

RUN pip install poetry
WORKDIR /app

# --- FIX: Copy from the root context ---
COPY pyproject.toml .

RUN poetry export --only "streamlit,requests,plotly" -f requirements.txt --output requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- FIX: Copy the *specific* service folder into /app ---
COPY ./services/frontend_darpan /app

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
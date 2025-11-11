FROM python:3.11-slim

RUN pip install poetry
WORKDIR /app

# --- FIX: Copy from the root context ---
COPY pyproject.toml .

RUN poetry export --only "fastapi,uvicorn,sqlalchemy,psycopg2-binary,redis" -f requirements.txt --output requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- FIX: Copy the *specific* service folder into /app ---
COPY ./services/api_setu /app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
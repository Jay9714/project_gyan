FROM python:3.11-slim

RUN apt-get update && apt-get install -y postgresql-client
RUN useradd -m appuser

WORKDIR /app

# --- FIX: Copy from the root context ---
COPY pyproject.toml .
RUN pip install poetry

RUN poetry export --only "celery,redis,sqlalchemy,psycopg2-binary,pandas,yfinance,ta,prophet,scikit-learn,tensorflow" -f requirements.txt --output requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# --- FIX: Copy the *specific* service folder into /app ---
COPY ./services/engine_astra /app

RUN chmod +x /app/wait-for-postgres.sh
RUN chown -R appuser:appuser /app

USER appuser
ENTRYPOINT ["/app/wait-for-postgres.sh"]
ENV PATH="/home/appuser/.local/bin:${PATH}"
CMD ["celery", "-A", "tasks", "worker", "--loglevel=info"]
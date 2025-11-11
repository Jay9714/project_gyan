FROM python:3.11-slim

RUN useradd -m appuser
WORKDIR /app

# --- FIX: Copy from the root context ---
COPY pyproject.toml .
RUN pip install poetry

RUN poetry export --only "celery,redis" -f requirements.txt --output requirements.txt
RUN pip install --user --no-cache-dir -r requirements.txt

# --- FIX: Copy the *specific* service folder into /app ---
COPY ./services/worker_chakra /app

RUN chown -R appuser:appuser /app
USER appuser

ENV PATH="/home/appuser/.local/bin:${PATH}"
CMD ["celery", "-A", "tasks", "beat", "--loglevel=info"]
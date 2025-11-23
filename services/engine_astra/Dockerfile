FROM python:3.11-slim

RUN apt-get update && apt-get install -y postgresql-client
RUN useradd -m appuser
WORKDIR /app

# Copy Requirements
COPY ./services/engine_astra/requirements.txt .

# Install Pip & Requirements
RUN pip install --upgrade pip
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

# --- FIX: Copy Shared Folder ---
COPY ./shared /app/shared
# -------------------------------

# Copy Service Code
COPY ./services/engine_astra /app

RUN chmod +x /app/wait-for-postgres.sh
RUN chown -R appuser:appuser /app

USER appuser
ENV PATH="/home/appuser/.local/bin:${PATH}"
ENTRYPOINT ["/app/wait-for-postgres.sh"]
CMD ["celery", "-A", "tasks", "worker", "--loglevel=info"]
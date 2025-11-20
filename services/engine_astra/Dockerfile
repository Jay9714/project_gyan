# services/engine_astra/Dockerfile
FROM python:3.11-slim

# 1. Install system dependencies (needed for pg_isready)
RUN apt-get update && apt-get install -y postgresql-client

# 2. Create a non-root user
RUN useradd -m appuser
WORKDIR /app

# 3. Copy requirements and install
# Note: This copies from ./services/engine_astra/requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copy the rest of the app code
COPY . .

# 5. Set permissions for the wait script
RUN chmod +x /app/wait-for-postgres.sh
RUN chown -R appuser:appuser /app

# 6. Switch to the non-root user
USER appuser

# 7. Add local bin to PATH (just in case)
ENV PATH="/home/appuser/.local/bin:${PATH}"

# 8. Set entrypoint to the wait script
ENTRYPOINT ["/app/wait-for-postgres.sh"]

# 9. Default command (can be overridden by docker-compose for migration)
CMD ["celery", "-A", "tasks", "worker", "--loglevel=info"]
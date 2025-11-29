FROM python:3.11-slim

# 1. Install system dependencies
RUN apt-get update && apt-get install -y postgresql-client curl git

# 2. Create non-root user
RUN useradd -m appuser
WORKDIR /app

# 3. Copy requirements
# We copy specifically from the service folder
COPY services/engine_astra/requirements.txt .

# 4. OPTIMIZED INSTALLATION PROCESS
# Upgrade pip
RUN pip install --upgrade pip

# Configure global timeout
RUN pip config set global.timeout 3000

# Step A: Install PyTorch CPU first
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

# Step B: Install Transformers
RUN pip install transformers

# Step C: Install the rest
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy Shared Code
COPY shared /app/shared

# 6. Copy Application Code
# We copy the CONTENTS of the engine_astra folder into /app
COPY services/engine_astra /app

# --- FIX: Explicitly copy the wait script to /app root ---
# This ensures it is exactly where we expect it
COPY services/engine_astra/wait-for-postgres.sh /app/wait-for-postgres.sh
# ---------------------------------------------------------

# 7. Set permissions
RUN chmod +x /app/wait-for-postgres.sh
RUN chown -R appuser:appuser /app

# 8. Configure User & Entrypoint
USER appuser
ENV PATH="/home/appuser/.local/bin:${PATH}"
# Ensure Python finds the shared folder
ENV PYTHONPATH="/app"

ENTRYPOINT ["/app/wait-for-postgres.sh"]
CMD ["celery", "-A", "tasks", "worker", "--loglevel=info"]
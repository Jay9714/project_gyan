FROM python:3.11-slim

RUN useradd -m appuser
WORKDIR /app

# --- FIX: Point to the specific requirements file, not the root one ---
COPY services/api_setu/requirements.txt .

# --- OPTIMIZED INSTALLATION ---
# 1. Upgrade pip
RUN pip install --upgrade pip

# 2. Configure timeout
RUN pip config set global.timeout 3000

# 3. Install the rest

# 4. Install the rest
RUN pip install --no-cache-dir -r requirements.txt
# ------------------------------

# Copy Shared Code
COPY shared /app/shared

# Copy App Code
COPY ./services/api_setu /app

RUN chown -R appuser:appuser /app
USER appuser

ENV PATH="/home/appuser/.local/bin:${PATH}"
# Ensure Python finds the shared folder
ENV PYTHONPATH="/app"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
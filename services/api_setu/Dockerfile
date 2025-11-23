FROM python:3.11-slim

RUN useradd -m appuser
WORKDIR /app

COPY ./services/api_setu/requirements.txt .

RUN pip install --upgrade pip
RUN pip install --default-timeout=1000 --no-cache-dir -r requirements.txt

# --- FIX: Copy Shared Folder ---
COPY ./shared /app/shared
# -------------------------------

COPY ./services/api_setu /app

RUN chown -R appuser:appuser /app
USER appuser

ENV PATH="/home/appuser/.local/bin:${PATH}"
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
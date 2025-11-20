FROM python:3.11-slim

RUN useradd -m appuser
WORKDIR /app

# Copy the local requirements.txt
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app code
COPY . .

RUN chown -R appuser:appuser /app
USER appuser

ENV PATH="/home/appuser/.local/bin:${PATH}"
CMD ["celery", "-A", "tasks", "beat", "--loglevel=info"]
# trigger_test.py
from celery import Celery
import os

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
app = Celery('chakra_tasks', broker=REDIS_URL)

print("Sending test pipeline job to Chakra...")

# --- THIS IS THE FIX ---
# Send this task specifically to the 'chakra_q'
app.send_task("chakra.run_test_pipeline", queue='chakra_q')
# --- END FIX ---

print("Job sent!")
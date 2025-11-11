# trigger_test.py
from celery import Celery
import os

REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

app = Celery('astra_tasks', broker=REDIS_URL)

print("Sending 'run_data_pipeline' job directly to Astra...")

app.send_task("astra.run_nightly_update", queue='astra_q')

print("Job sent!")
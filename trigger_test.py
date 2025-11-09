# trigger_test.py
from celery import Celery
import os

# We are now connecting directly to the 'astra_tasks' app
# so we can send a job to its queue.
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Note: The app name MUST match the worker we are sending to.
app = Celery('astra_tasks', broker=REDIS_URL)

print("Sending 'run_data_pipeline' job directly to Astra...")

# This sends the 'astra.run_data_pipeline' task
# specifically to the 'astra_q' queue, which the AIBrain is listening to.
app.send_task("astra.run_data_pipeline", queue='astra_q')

print("Job sent!")
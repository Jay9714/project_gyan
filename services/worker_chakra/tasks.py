# services/worker_chakra/tasks.py
import os
from celery import Celery
from celery.schedules import crontab 

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
app = Celery('chakra_tasks', broker=REDIS_URL, backend=REDIS_URL)

# --- THIS IS THE FIX ---
# Tell this worker to ONLY listen to its own queue
app.conf.task_default_queue = 'chakra_q'
# --- END FIX ---

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    print("Chakra: Setting up nightly schedule...")
    
    sender.add_periodic_task(
        crontab(hour=1, minute=0),
        # --- THIS IS THE FIX ---
        # Send this job specifically to the 'astra_q'
        app.send_task("astra.run_data_pipeline", queue='astra_q'),
        # --- END FIX ---
        name='Run Nightly Data Pipeline'
    )
    print("Chakra: Nightly schedule set for 1:00 AM.")
        
@app.task(name="chakra.run_test_pipeline")
def run_test_pipeline():
    print("Chakra: MANUAL TEST triggered. Sending job to Astra...")
    # --- THIS IS THE FIX ---
    # Send this job specifically to the 'astra_q'
    app.send_task("astra.run_data_pipeline", queue='astra_q')
    # --- END FIX ---
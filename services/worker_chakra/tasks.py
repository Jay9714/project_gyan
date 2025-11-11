# services/worker_chakra/tasks.py
import os
from celery import Celery
from celery.schedules import crontab 

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
app = Celery('chakra_tasks', broker=REDIS_URL, backend=REDIS_URL)

app.conf.task_default_queue = 'chakra_q'

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """
    This is the main scheduler.
    Its ONLY job is to send the nightly task.
    """
    print("Chakra: Setting up nightly schedule...")
    
    sender.add_periodic_task(
        crontab(hour=1, minute=0),
        app.send_task.s("astra.run_nightly_update", queue='astra_q'),
        name='Run Nightly Data & Analysis Pipeline'
    )
    
    print("Chakra: Nightly schedule set for 1:00 AM.")
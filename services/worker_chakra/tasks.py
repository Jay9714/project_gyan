import os
from celery import Celery

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
app = Celery('chakra_tasks', broker=REDIS_URL, backend=REDIS_URL)

@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Test job: print a message every 30 seconds
    sender.add_periodic_task(30.0, hello_chakra.s(), name='Hello Chakra every 30s')

@app.task(name="chakra.hello")
def hello_chakra():
    print("Chakra: Scheduling tick... sending job to Astra...")
    # This is how we will call the *other* service
    app.send_task("astra.hello")
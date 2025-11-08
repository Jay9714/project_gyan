import os
from celery import Celery

REDIS_URL = os.environ.get('REDIS_URL', 'redis://redis:6379/0')
app = Celery('astra_tasks', broker=REDIS_URL, backend=REDIS_URL)

@app.task(name="astra.hello")
def hello_astra():
    print("Astra: Hello! My brain is online.")
    return "Astra is running"
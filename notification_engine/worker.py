import os
import redis
from rq import Worker, Queue

listen = ['notification_tasks']

# Connect using the same environment variable as models.py
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6380")
conn = redis.from_url(REDIS_URL)

if __name__ == '__main__':
    print(f"--- Notification Worker Starting (Redis: {REDIS_URL}) ---")
    # Create queues with explicit connection to satisfy RQ 2.x requirements
    queues = [Queue(name, connection=conn) for name in listen]
    
    # Pass the list of queues to the Worker
    worker = Worker(queues, connection=conn)
    worker.work()


from redis import Redis
from rq import Queue, Worker
from rq.registry import FailedJobRegistry

redis_conn = Redis(host='localhost', port=6379, db=0)
q = Queue('etl_queue', connection=redis_conn)
registry = FailedJobRegistry(queue=q)

job_ids = registry.get_job_ids()
print(f"Failed jobs count: {len(job_ids)}")

for job_id in job_ids:
    job = q.fetch_job(job_id)
    if job:
        print(f"\n--- Job {job_id} ---")
        print(f"Status: {job.get_status()}")
        print(f"Enqueued at: {job.enqueued_at}")
        print(f"Exc info: {job.exc_info}")
    else:
        print(f"Job {job_id} not found")

"""jobs.queue.pool — ARQ pool management (delegates to job_queue for shared state).

Import of _get_redis_settings from jobs.queue.config (not job_queue) breaks
the circular chain: job_queue → jobs.queue.config → jobs.queue.__init__ → pool → job_queue.
"""
from job_queue import (  # noqa: F401
    get_arq_pool,
    close_arq_pool,
    _check_worker_alive,
    is_queue_available,
    get_queue_health,
    enqueue_job,
)
from jobs.queue.config import _get_redis_settings  # noqa: F401

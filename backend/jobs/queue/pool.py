"""jobs.queue.pool — ARQ pool management (delegates to job_queue for shared state).

Import _get_redis_settings from the config submodule directly to avoid a
circular import chain: jobs.queue.pool → job_queue → jobs.queue.config (↓)
                                                                        jobs.queue.pool (↑)
"""
from jobs.queue.config import _get_redis_settings  # noqa: F401
from job_queue import (  # noqa: F401
    get_arq_pool,
    close_arq_pool,
    _check_worker_alive,
    is_queue_available,
    get_queue_health,
    enqueue_job,
)

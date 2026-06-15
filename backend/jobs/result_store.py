"""jobs.result_store — Job result persistence (Redis/cancel flags).

Re-exports result store functions from jobs.queue.result_store (TD-1875).
"""
from jobs.queue.result_store import (  # noqa: F401
    persist_job_result,
    get_job_result,
    set_cancel_flag,
    check_cancel_flag,
    clear_cancel_flag,
)
from job_queue import enqueue_job  # noqa: F401

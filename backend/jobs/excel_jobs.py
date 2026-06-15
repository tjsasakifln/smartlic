"""jobs.excel_jobs — Excel generation async jobs.

Re-exports Excel job functions from jobs.queue (TD-1875).
"""
from jobs.queue.jobs import (  # noqa: F401
    excel_generation_job,
)
from jobs.queue.result_store import (  # noqa: F401
    _update_results_excel_url,
)

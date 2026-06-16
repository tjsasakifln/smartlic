"""jobs.search_jobs — Search pipeline async jobs.

Re-exports search job functions from jobs.queue (TD-1875).
"""
from jobs.queue.search import (  # noqa: F401
    search_job,
    _persist_search_results_to_redis,
    _persist_search_results_to_supabase,
    _update_search_session,
)
from jobs.queue.result_store import (  # noqa: F401
    acquire_search_slot,
    release_search_slot,
)

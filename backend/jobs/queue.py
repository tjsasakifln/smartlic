"""jobs.queue — aggregated re-exports for backward compatibility (TD-1875).

Re-exports from ``job_queue`` (real functions) and ``jobs.queue.*`` submodules.
Import from ``job_queue`` directly for pool + enqueue functions.
"""
from job_queue import (  # noqa: F401
    get_arq_pool, close_arq_pool, enqueue_job,
    is_queue_available, get_queue_health,
    _arq_pool, _pool_lock, _check_worker_alive,
)
from jobs.queue.result_store import (  # noqa: F401
    _CANCEL_KEY_PREFIX, _CANCEL_TTL,
    _CONCURRENT_SEARCH_KEY_PREFIX, _CONCURRENT_SEARCH_TTL,
    _PENDING_REVIEW_KEY_PREFIX, _ZERO_MATCH_KEY_PREFIX,
    set_cancel_flag, check_cancel_flag, clear_cancel_flag,
    persist_job_result, get_job_result, _update_results_excel_url,
    acquire_search_slot, release_search_slot,
    store_pending_review_bids, store_zero_match_results, get_zero_match_results,
)
from jobs.queue.jobs import (  # noqa: F401
    llm_summary_job, excel_generation_job, bid_analysis_job,
    daily_digest_job, email_alerts_job,
    reclassify_pending_bids_job, classify_zero_match_job,
    generate_intel_report,
)
from jobs.cron.send_lead_magnet import (  # noqa: F401
    send_lead_magnet_job,
    send_lead_magnet_batch_job,
)
from jobs.queue.search import (  # noqa: F401
    search_job, _persist_search_results_to_redis,
    _persist_search_results_to_supabase, _update_search_session,
)
from jobs.queue.config import (  # noqa: F401
    _worker_redis_settings, _worker_cron_jobs, _worker_on_startup, WorkerSettings,
)

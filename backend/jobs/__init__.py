"""jobs package — DEBT-305 decomposition.

Provides organized import paths for job/cron-related modules:

  Queue management:
    - jobs.pool — ARQ connection pool lifecycle
    - jobs.result_store — Job result persistence, cancel flags, enqueue

  Job functions (ARQ worker):
    - jobs.jobs — LLM summary, reclassification
    - jobs.search_jobs — Search pipeline execution
    - jobs.zero_match_jobs — Zero-match classification
    - jobs.notification_jobs — Email alerts, daily digest

  Cron tasks (lifespan background loops):
    - jobs.cron — aggregated re-exports from jobs.cron.*
    - jobs.cron.canary — PNCP health canary
    - jobs.cron.billing — Billing reconciliation
    - jobs.cron.notifications — Alerts, trial sequence, SLA, volume

Import from ``jobs.cron.`` or ``job_queue`` directly.
Previous cron_jobs facade has been removed (TD-1875).
"""

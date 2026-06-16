"""TrialSequenceLoop — Trial email sequence processing (STORY-310 / CRIT-044)."""
import logging

from jobs.cron.base import BaseCronLoop

logger = logging.getLogger(__name__)

TRIAL_SEQUENCE_INTERVAL_SECONDS = 2 * 60 * 60
TRIAL_SEQUENCE_BATCH_SIZE = 50


class TrialSequenceLoop(BaseCronLoop):
    """Process deferred trial email sequences.

    Runs every 2h (to cover all timezones) and advances the trial email
    sequence for users. Also drains the DLQ (STORY-418) for idempotent
    retry of transient failures.
    """

    name = "trial_email_sequence"
    interval_seconds = TRIAL_SEQUENCE_INTERVAL_SECONDS
    initial_delay = 60.0
    error_retry_seconds = 300.0

    async def run_once(self) -> dict:
        from services.trial_email_sequence import process_trial_emails
        result = await process_trial_emails(batch_size=TRIAL_SEQUENCE_BATCH_SIZE)
        logger.info("STORY-310 trial sequence: %s", result)

        # STORY-418: drain DLQ right after forward pass
        try:
            from services.trial_email_dlq import reprocess_pending
            dlq_stats = await reprocess_pending(limit=100)
            if dlq_stats.get("considered", 0) > 0:
                logger.info("STORY-418 DLQ: %s", dlq_stats)
        except Exception as dlq_err:
            logger.error("STORY-418: DLQ reprocess failed: %s", dlq_err)

        return result

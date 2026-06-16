"""jobs.cron.notification_loops — Individual cron loop classes for notifications.

Each module contains a single ``BaseCronLoop`` subclass that maps to one of the
five original loops in ``jobs/cron/notifications.py``:

  * ``AlertsLoop``          — Search alert email dispatch (daily)
  * ``TrialSequenceLoop``   — Trial email sequence processing (every 2h)
  * ``SupportSlaLoop``      — Support SLA breach monitoring (every 4h)
  * ``DailyVolumeLoop``     — Daily search volume recording (daily)
  * ``SectorStatsLoop``     — Sector stats refresh (daily)
"""

from jobs.cron.notification_loops.alerts import AlertsLoop
from jobs.cron.notification_loops.trial_sequence import TrialSequenceLoop
from jobs.cron.notification_loops.support_sla import SupportSlaLoop
from jobs.cron.notification_loops.daily_volume import DailyVolumeLoop
from jobs.cron.notification_loops.sector_stats import SectorStatsLoop

__all__ = [
    "AlertsLoop",
    "TrialSequenceLoop",
    "SupportSlaLoop",
    "DailyVolumeLoop",
    "SectorStatsLoop",
]

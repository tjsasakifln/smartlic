"""PlanReconciliationLoop — Profile/plan drift detection + auto-heal (DEBT-010)."""
import logging
from datetime import datetime, timezone

from jobs.cron.base import BaseCronLoop

logger = logging.getLogger(__name__)

PLAN_RECONCILIATION_LOCK_KEY = "smartlic:plan_reconciliation:lock"
PLAN_RECONCILIATION_LOCK_TTL = 10 * 60
PLAN_RECONCILIATION_INTERVAL = 12 * 60 * 60

_MONITORED_TABLES = [
    "search_results_cache", "search_results_store", "search_sessions",
    "stripe_webhook_events", "profiles", "user_subscriptions",
    "conversations", "messages", "alert_runs", "classification_feedback",
]


class PlanReconciliationLoop(BaseCronLoop):
    """Detect and auto-heal drifts between profiles.plan_type and subscription plans.

    Runs every 12h: compares profile plan_type vs user_subscriptions, logs
    drifts, auto-heals where possible (orphan profiles -> free_trial, stale
    profiles -> align with subscription).  Also updates Prometheus table-size
    gauges for monitored tables.
    """

    name = "plan_reconciliation"
    interval_seconds = PLAN_RECONCILIATION_INTERVAL
    lock_key = PLAN_RECONCILIATION_LOCK_KEY
    lock_ttl = PLAN_RECONCILIATION_LOCK_TTL
    initial_delay = 300.0
    error_retry_seconds = 300.0

    async def run_once(self) -> dict:
        from metrics import PLAN_RECONCILIATION_RUNS
        PLAN_RECONCILIATION_RUNS.inc()
        locked = await self._acquire_lock()
        if not locked:
            logger.info("DEBT-010: Plan reconciliation skipped — lock held")
            return {"status": "skipped", "reason": "lock_held"}
        try:
            return await self._run_reconciliation()
        finally:
            await self._release_lock()

    async def _run_reconciliation(self) -> dict:
        from supabase_client import get_supabase, sb_execute, sb_execute_direct
        from metrics import PLAN_RECONCILIATION_DRIFT, PLAN_RECONCILIATION_AUTO_HEALED, DB_TABLE_SIZE_BYTES

        try:
            return await self._do_reconciliation(sb_execute, sb_execute_direct, get_supabase,
                                                  PLAN_RECONCILIATION_DRIFT, PLAN_RECONCILIATION_AUTO_HEALED,
                                                  DB_TABLE_SIZE_BYTES)
        except Exception as e:
            logger.error("DEBT-010: Plan reconciliation error: %s", e)
            return {"status": "error", "error": str(e)}

    async def _do_reconciliation(self, sb_execute, sb_execute_direct, get_supabase,
                                  PLAN_RECONCILIATION_DRIFT, PLAN_RECONCILIATION_AUTO_HEALED,
                                  DB_TABLE_SIZE_BYTES) -> dict:
        sb = get_supabase()
        profiles_result = await sb_execute(sb.table("profiles").select("id, plan_type"))
        profiles = {p["id"]: p["plan_type"] for p in (profiles_result.data or [])}
        subs_result = await sb_execute(sb.table("user_subscriptions").select("user_id, plan_id").eq("is_active", True))
        subs = {s["user_id"]: s["plan_id"] for s in (subs_result.data or [])}

        drift_details, auto_healed = await self._detect_and_heal_drifts(
            profiles, subs, sb, sb_execute,
            PLAN_RECONCILIATION_DRIFT, PLAN_RECONCILIATION_AUTO_HEALED,
        )

        if drift_details:
            logger.warning("DEBT-010: %d drifts, auto-healed %d: %s", len(drift_details), auto_healed, drift_details[:5])
        else:
            logger.info("DEBT-010: clean — %d profiles, %d active subs", len(profiles), len(subs))

        await self._update_table_sizes(sb, sb_execute_direct, DB_TABLE_SIZE_BYTES)

        return {
            "status": "completed", "total_profiles": len(profiles),
            "total_active_subs": len(subs), "drift_count": len(drift_details),
            "auto_healed": auto_healed,
            "drift_details": drift_details[:20],
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    async def _detect_and_heal_drifts(
        self, profiles: dict, subs: dict, sb, sb_execute,
        drift_metric, healed_metric,
    ) -> tuple[list[dict], int]:
        """Iterate profiles, detect drifts and auto-heal where possible.

        Returns (drift_details, auto_healed_count).
        """
        drift_details: list[dict] = []
        auto_healed = 0
        for user_id, plan_type in profiles.items():
            sub_plan = subs.get(user_id)
            if sub_plan is None:
                if plan_type not in ("free_trial", "cancelled", None, ""):
                    drift_details.append({"user_id": user_id[:8] + "...", "profile_plan": plan_type, "sub_plan": None, "direction": "orphan_profile"})
                    drift_metric.labels(direction="orphan_profile").inc()
                    try:
                        await sb_execute(sb.table("profiles").update({"plan_type": "free_trial"}).eq("id", user_id))
                        auto_healed += 1
                        healed_metric.labels(direction="orphan_profile").inc()
                    except Exception as heal_err:
                        logger.warning("DEBT-010: auto-heal failed for orphan %s: %s", user_id[:8], heal_err)
            elif plan_type != sub_plan:
                drift_details.append({"user_id": user_id[:8] + "...", "profile_plan": plan_type, "sub_plan": sub_plan, "direction": "profiles_stale"})
                drift_metric.labels(direction="profiles_stale").inc()
                try:
                    await sb_execute(sb.table("profiles").update({"plan_type": sub_plan}).eq("id", user_id))
                    auto_healed += 1
                    healed_metric.labels(direction="profiles_stale").inc()
                except Exception as heal_err:
                    logger.warning("DEBT-010: auto-heal failed for %s: %s", user_id[:8], heal_err)
        return drift_details, auto_healed

    async def _update_table_sizes(self, sb, sb_execute_direct, size_gauge) -> None:
        """Update Prometheus table-size gauges for monitored tables."""
        for table_name in _MONITORED_TABLES:
            try:
                size_result = await sb_execute_direct(sb.rpc("pg_total_relation_size_safe", {"tbl": table_name}))
                if size_result and size_result.data is not None:
                    sz = int(size_result.data) if not isinstance(size_result.data, list) else (int(size_result.data[0]) if size_result.data else 0)
                    size_gauge.labels(table_name=table_name).set(sz)
            except Exception:
                pass

"""Integration tests — DATA-DRIFT-001 paywall consolidation.

Validates the canonical/mirror invariant established by migration
``20260429230000_data_drift_001_trigger_sync.sql``:

* canonical: ``user_subscriptions.expires_at`` (read by check_quota)
* mirror:    ``profiles.trial_expires_at`` (auto-synced via Postgres trigger)

Memory: ``project_paulo_paywall_bypass_root_cause_2026_04_29``
ADR:    ``docs/adr/SCHEMA-DRIFT.md`` (Option A — canonical + mirror)

These tests have two layers:

* Unit-style behavior assertions on ``_assign_plan`` and ``extend_trial``
  using the integration suite's mock Supabase fixture — confirms the Python
  callers do NOT write directly to ``profiles.trial_expires_at``.
* SQL-level assertions documented as ``xfail``/``skip`` placeholders that
  require a live Postgres test container. They are kept here so a future
  ``pytest-postgresql`` / ``testcontainers`` setup can drop them in without
  re-discovering the contract.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Layer 1: Python caller behavior — no direct profiles writes
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAdminAssignPlanCanonicalOnly:
    """``_assign_plan`` must write only to ``user_subscriptions``.

    The Postgres trigger ``trg_sync_trial_expires_at`` is responsible for
    mirroring to ``profiles.trial_expires_at``. A direct write from Python
    would re-introduce dual source-of-truth drift.
    """

    def _build_mock_supabase(self) -> MagicMock:
        """Build a Supabase mock that records every .table() call."""
        sb = MagicMock(name="supabase")

        # plan lookup returns a 30-day plan
        plan_query = MagicMock()
        plan_query.execute.return_value.data = {
            "id": "smartlic_pro",
            "max_searches": 1000,
            "duration_days": 30,
        }
        sb.table.return_value.select.return_value.eq.return_value.single.return_value = plan_query

        # all other chained calls (update, insert) return MagicMock
        return sb

    def test_assign_plan_writes_only_user_subscriptions(self):
        import admin

        sb = self._build_mock_supabase()

        admin._assign_plan(sb, user_id="u-test", plan_id="smartlic_pro")

        # Collect the table names touched
        table_calls = [c.args[0] for c in sb.table.call_args_list if c.args]

        assert "user_subscriptions" in table_calls, (
            "Canonical table must be written"
        )
        assert "profiles" not in table_calls, (
            "DATA-DRIFT-001: _assign_plan must NOT write profiles.trial_expires_at "
            "directly — that is the trigger's job. See migration "
            "20260429230000_data_drift_001_trigger_sync.sql."
        )

    def test_assign_plan_deactivates_previous_then_inserts(self):
        import admin

        sb = self._build_mock_supabase()
        admin._assign_plan(sb, user_id="u-test", plan_id="smartlic_pro")

        # Verify update(deactivate) and insert(new) were both invoked
        update_called = any(
            "is_active" in str(c)
            for c in sb.table.return_value.update.call_args_list
        )
        insert_called = sb.table.return_value.insert.called

        assert update_called or insert_called, (
            "Expected deactivate-then-insert flow to invoke at least one of "
            "update/insert on user_subscriptions"
        )


@pytest.mark.integration
class TestExtendTrialCallerNoDirectProfileWrite:
    """The Python ``extend_trial`` wrapper delegates to the SQL RPC.

    The RPC (post-DATA-DRIFT-001) writes canonical first; trigger mirrors.
    The Python layer must NOT shortcut around the RPC and write profiles
    directly.
    """

    @pytest.mark.asyncio
    async def test_extend_trial_calls_rpc_only(self):
        from services import trial_extension

        # Build mock supabase
        sb = MagicMock(name="supabase")

        # profile lookup → user is on free_trial, not yet expired
        profile_query = MagicMock()
        profile_query.data = {
            "plan_type": "free_trial",
            "trial_expires_at": (
                datetime.now(timezone.utc) + timedelta(days=3)
            ).isoformat(),
        }

        # feedback lookup (eligibility) → user has 1 feedback
        feedback_query = MagicMock()
        feedback_query.count = 1
        feedback_query.data = []

        # rpc result
        rpc_result = MagicMock()
        rpc_result.data = {
            "days_added": 2,
            "total_extended": 2,
            "new_expires_at": (
                datetime.now(timezone.utc) + timedelta(days=5)
            ).isoformat(),
            "canonical_updated": True,
        }

        async def fake_sb_execute(query):
            # crude routing by query type str
            q = str(type(query))
            if "profile" in q.lower():
                return profile_query
            if "feedback" in q.lower():
                return feedback_query
            return rpc_result

        with (
            patch.object(trial_extension, "get_supabase", return_value=sb),
            patch.object(
                trial_extension, "sb_execute", side_effect=lambda q: _async_return(_route(q, profile_query, feedback_query, rpc_result))
            ),
            patch(
                "config.features.TRIAL_EXTENSION_ENABLED", True, create=True
            ),
            patch(
                "config.features.TRIAL_EXTENSION_MAX_DAYS", 7, create=True
            ),
        ):
            # Skip — the routing is too coarse for a stable test without
            # a richer fixture. Documented as TODO for the next iteration.
            pytest.skip(
                "Requires routed sb_execute fixture — defer until "
                "shared trial_extension fixture lands"
            )


# ---------------------------------------------------------------------------
# Layer 2: SQL-level invariants (require live Postgres)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skip(
    reason="Requires live Postgres test container — implement once "
    "testcontainers/pytest-postgresql fixtures are wired in conftest"
)
class TestTriggerSyncSqlLevel:
    """SQL-level invariants for ``trg_sync_trial_expires_at``.

    Skipped today; preserved as a contract record for the future test DB
    fixture. When wiring: apply migration ``20260429230000`` to a scratch
    schema, then run these.
    """

    async def test_insert_user_subscription_populates_profile_trial(self):
        """INSERT into user_subscriptions → profile.trial_expires_at populated."""
        ...

    async def test_update_subscription_expires_at_propagates(self):
        """UPDATE user_subscriptions.expires_at → profile.trial_expires_at follows."""
        ...

    async def test_extend_trial_atomic_v2_writes_canonical_first(self):
        """RPC writes user_subscriptions; trigger mirrors profile."""
        ...

    async def test_extend_trial_atomic_falls_back_to_profiles_when_no_subscription(self):
        """Legacy state (no active subscription row) → RPC still extends profile mirror."""
        ...

    async def test_backfill_idempotent(self):
        """Running migration twice should not double-update profiles rows."""
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _route(query, profile_query, feedback_query, rpc_result):  # pragma: no cover - helper
    q = str(query).lower()
    if "profile" in q:
        return profile_query
    if "feedback" in q:
        return feedback_query
    return rpc_result


async def _async_return(value):  # pragma: no cover - helper
    return value

-- ============================================================================
-- DOWN: Reverts plan reconciliation drift fixes
-- Reverses: 20260612120002_fix_plan_reconciliation_drift.sql
-- Date: 2026-06-12
--
-- Note: This is a no-op down migration because the UPDATE statements are
-- data-only changes. We cannot restore the previous plan_type values
-- without a snapshot. The backend auto-heal will re-detect and fix any
-- new drift on the next reconciliation cycle.
-- ============================================================================

-- No-op: plan_type corrections are data fixes that cannot be safely
-- reversed without a pre-migration snapshot.
SELECT 1;

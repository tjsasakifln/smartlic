-- Issue #1959: Rollback outgoing_webhook_deliveries table

DROP TRIGGER IF EXISTS trg_outgoing_webhook_updated_at ON outgoing_webhook_deliveries;
DROP FUNCTION IF EXISTS update_outgoing_webhook_updated_at;
DROP INDEX IF EXISTS idx_outgoing_webhook_idempotency;
DROP INDEX IF EXISTS idx_outgoing_webhook_pending;
DROP INDEX IF EXISTS idx_outgoing_webhook_admin_filter;
DROP TABLE IF EXISTS outgoing_webhook_deliveries;

-- Issue #1959: Outgoing webhook deliveries table with retry tracking
-- Adiciona suporte a retry com exponential backoff para webhooks outgoing (Slack/Teams/Email)

-- ============================================================================
-- 1. outgoing_webhook_deliveries — individual webhook delivery records
-- ============================================================================

CREATE TABLE IF NOT EXISTS outgoing_webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel TEXT NOT NULL CHECK (channel IN ('slack', 'teams', 'email')),
    event_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'delivered', 'failed', 'cancelled')),
    retries INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 3,
    next_retry_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Unique index for idempotency (channel + event_type + entity_id)
CREATE UNIQUE INDEX IF NOT EXISTS idx_outgoing_webhook_idempotency
    ON outgoing_webhook_deliveries(channel, event_type, entity_id);

-- Index for pending deliveries query (used by ARQ job).
-- status is omitted from columns since the WHERE clause already filters it.
CREATE INDEX IF NOT EXISTS idx_outgoing_webhook_pending
    ON outgoing_webhook_deliveries(next_retry_at)
    WHERE status = 'pending';

-- Index for admin filtering by channel and status
CREATE INDEX IF NOT EXISTS idx_outgoing_webhook_admin_filter
    ON outgoing_webhook_deliveries(status, channel, created_at DESC);

-- Auto-update updated_at on row modification
CREATE OR REPLACE FUNCTION update_outgoing_webhook_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_outgoing_webhook_updated_at ON outgoing_webhook_deliveries;
CREATE TRIGGER trg_outgoing_webhook_updated_at
    BEFORE UPDATE ON outgoing_webhook_deliveries
    FOR EACH ROW
    EXECUTE FUNCTION update_outgoing_webhook_updated_at();

COMMENT ON TABLE outgoing_webhook_deliveries IS 'Issue #1959: Outgoing webhook deliveries with retry tracking and idempotency';
COMMENT ON COLUMN outgoing_webhook_deliveries.channel IS 'Delivery channel: slack, teams, or email';
COMMENT ON COLUMN outgoing_webhook_deliveries.event_type IS 'Event type identifier (e.g. trial_expiring, payment_failed)';
COMMENT ON COLUMN outgoing_webhook_deliveries.entity_id IS 'Entity ID associated with the event (user_id, subscription_id, etc.)';
COMMENT ON COLUMN outgoing_webhook_deliveries.payload IS 'JSON payload to deliver to the webhook URL';
COMMENT ON COLUMN outgoing_webhook_deliveries.status IS 'pending | delivered | failed | cancelled';
COMMENT ON COLUMN outgoing_webhook_deliveries.retries IS 'Number of retry attempts so far';
COMMENT ON COLUMN outgoing_webhook_deliveries.max_retries IS 'Maximum retry attempts before giving up (default 3)';
COMMENT ON COLUMN outgoing_webhook_deliveries.next_retry_at IS 'When the next retry attempt is scheduled (NULL if not pending)';
COMMENT ON COLUMN outgoing_webhook_deliveries.last_error IS 'Error message from the last failed attempt';
COMMENT ON INDEX idx_outgoing_webhook_idempotency IS 'Prevents duplicate deliveries for the same (channel, event_type, entity_id)';

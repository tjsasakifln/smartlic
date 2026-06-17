CREATE TABLE IF NOT EXISTS integrations_webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    channel TEXT NOT NULL CHECK (channel IN ('slack', 'teams', 'email')),
    label TEXT,
    webhook_url TEXT,
    email_target TEXT,
    events TEXT[] DEFAULT '{}',
    is_active BOOLEAN DEFAULT true,
    last_triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE integrations_webhooks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can CRUD own webhooks" ON integrations_webhooks
    FOR ALL USING (auth.uid() = user_id);

CREATE INDEX IF NOT EXISTS idx_integrations_webhooks_user ON integrations_webhooks(user_id);

COMMENT ON TABLE integrations_webhooks IS 'Webhook integrations for Slack, Teams, Email notification channels (#1522)';
COMMENT ON COLUMN integrations_webhooks.channel IS 'Notification channel: slack, teams, or email';
COMMENT ON COLUMN integrations_webhooks.webhook_url IS 'Incoming webhook URL for Slack/Teams channels';
COMMENT ON COLUMN integrations_webhooks.email_target IS 'Target email address for email channel';
COMMENT ON COLUMN integrations_webhooks.events IS 'Array of event types to notify for: new_edital, deadline_24h, deadline_6h, deadline_1h, pregao_started, result_published';
COMMENT ON COLUMN integrations_webhooks.last_triggered_at IS 'Timestamp of last notification sent (used for rate limiting)';

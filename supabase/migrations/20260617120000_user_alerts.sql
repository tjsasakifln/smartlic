-- B2GOPS-011 (#1281): User alerts table + alert preferences
-- Wave 1 of EPIC-B2GOPS (#1262) — Intelligent Alert System

-- ============================================================================
-- 1. user_alerts — individual in-app alert records
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    type TEXT NOT NULL CHECK (type IN (
        'new_matching_edital', 'deadline_approaching', 'pregao_starting',
        'result_published', 'contrato_firmado', 'documento_vencendo'
    )),
    title TEXT NOT NULL,
    body TEXT,
    data JSONB DEFAULT '{}'::jsonb,
    is_read BOOLEAN DEFAULT false,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index for unread count queries
CREATE INDEX IF NOT EXISTS idx_user_alerts_unread
    ON user_alerts(user_id, created_at DESC)
    WHERE NOT is_read;

-- Index for type-based filtering
CREATE INDEX IF NOT EXISTS idx_user_alerts_type
    ON user_alerts(user_id, type)
    WHERE NOT is_read;

-- RLS
ALTER TABLE user_alerts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can see own alerts"
    ON user_alerts FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can update own alerts"
    ON user_alerts FOR UPDATE
    USING (auth.uid() = user_id);

CREATE POLICY "Users can delete own alerts"
    ON user_alerts FOR DELETE
    USING (auth.uid() = user_id);

COMMENT ON TABLE user_alerts IS 'B2GOPS-011: In-app user alert records with read/unread status';
COMMENT ON COLUMN user_alerts.type IS 'Alert event type: new_matching_edital, deadline_approaching, pregao_starting, result_published, contrato_firmado, documento_vencendo';
COMMENT ON COLUMN user_alerts.data IS 'JSON payload with related entity IDs, URLs, metadata';
COMMENT ON COLUMN user_alerts.is_read IS 'Read/unread status for badge counting';

-- ============================================================================
-- 2. user_alert_preferences — notification channel + type preferences
-- ============================================================================

CREATE TABLE IF NOT EXISTS user_alert_preferences (
    user_id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    channels JSONB DEFAULT '{"in_app": true}'::jsonb,
    enabled_types TEXT[] DEFAULT '{}'::text[],
    quiet_hours JSONB DEFAULT '{"start": null, "end": null}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE user_alert_preferences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own preferences"
    ON user_alert_preferences FOR ALL
    USING (auth.uid() = user_id);

COMMENT ON TABLE user_alert_preferences IS 'B2GOPS-011: User notification channel and alert type preferences';
COMMENT ON COLUMN user_alert_preferences.channels IS 'Enabled channels (e.g. {"in_app": true, "email": true})';
COMMENT ON COLUMN user_alert_preferences.enabled_types IS 'Whitelist of enabled alert types. Empty = all enabled.';
COMMENT ON COLUMN user_alert_preferences.quiet_hours IS 'Quiet hours config {"start": "22:00", "end": "07:00"} or null';

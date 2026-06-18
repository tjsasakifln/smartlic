-- B2GOPS-011 (#2021): Workspace watchlist table
-- Tracks editais that users want to monitor for alerts

CREATE TABLE IF NOT EXISTS workspace_watchlist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    edital_id TEXT NOT NULL,
    uf TEXT NOT NULL DEFAULT '',
    setor TEXT NOT NULL DEFAULT '',
    keywords TEXT[] DEFAULT '{}'::text[],
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Prevent duplicate watchlist entries per user for the same edital
CREATE UNIQUE INDEX IF NOT EXISTS idx_workspace_watchlist_user_edital
    ON workspace_watchlist(user_id, edital_id);

-- Index for user-based listing
CREATE INDEX IF NOT EXISTS idx_workspace_watchlist_user
    ON workspace_watchlist(user_id, created_at DESC);

-- RLS
ALTER TABLE workspace_watchlist ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can manage own watchlist"
    ON workspace_watchlist FOR ALL
    USING (auth.uid() = user_id);

COMMENT ON TABLE workspace_watchlist IS 'B2GOPS-011: User workspace watchlist — editais being monitored for alerts';
COMMENT ON COLUMN workspace_watchlist.edital_id IS 'PNCP ID or other source identifier for the edital';
COMMENT ON COLUMN workspace_watchlist.uf IS 'Estado da licitação (UF)';
COMMENT ON COLUMN workspace_watchlist.setor IS 'Setor para matching de alertas';
COMMENT ON COLUMN workspace_watchlist.keywords IS 'Additional keywords for alert matching';

-- B2GOPS-014 (#2024): Timeline Intelligence — feed cronológico de eventos do edital
-- Tabela de eventos de timeline por edital, vinculada ao usuário

-- ============================================================================
-- workspace_timeline_eventos — eventos cronológicos de cada edital
-- ============================================================================

CREATE TABLE IF NOT EXISTS workspace_timeline_eventos (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    edital_id TEXT NOT NULL,
    user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN (
        'publicacao', 'alteracao', 'impugnacao', 'esclarecimento',
        'resultado', 'homologacao', 'nota_manual', 'lembrete'
    )),
    titulo TEXT NOT NULL,
    descricao TEXT,
    critico BOOLEAN DEFAULT false,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Index para consulta por edital + ordenação cronológica DESC
CREATE INDEX IF NOT EXISTS idx_timeline_eventos_edital
    ON workspace_timeline_eventos(edital_id, created_at DESC);

-- Index para consulta por usuário + ordenação cronológica DESC
CREATE INDEX IF NOT EXISTS idx_timeline_eventos_user
    ON workspace_timeline_eventos(user_id, created_at DESC);

-- Index para filtro por tipo
CREATE INDEX IF NOT EXISTS idx_timeline_eventos_tipo
    ON workspace_timeline_eventos(edital_id, tipo);

-- Index para filtro por crítico
CREATE INDEX IF NOT EXISTS idx_timeline_eventos_critico
    ON workspace_timeline_eventos(edital_id, critico)
    WHERE critico = true;

-- RLS
ALTER TABLE workspace_timeline_eventos ENABLE ROW LEVEL SECURITY;

-- Política: usuário só vê próprios eventos
CREATE POLICY "Usuarios veem proprios eventos"
    ON workspace_timeline_eventos FOR SELECT
    USING (auth.uid() = user_id);

-- Política: usuário cria próprios eventos
CREATE POLICY "Usuarios criam proprios eventos"
    ON workspace_timeline_eventos FOR INSERT
    WITH CHECK (auth.uid() = user_id);

-- Política: usuário atualiza próprios eventos
CREATE POLICY "Usuarios atualizam proprios eventos"
    ON workspace_timeline_eventos FOR UPDATE
    USING (auth.uid() = user_id);

-- Política: usuário deleta próprios eventos
CREATE POLICY "Usuarios deletam proprios eventos"
    ON workspace_timeline_eventos FOR DELETE
    USING (auth.uid() = user_id);

COMMENT ON TABLE workspace_timeline_eventos IS 'B2GOPS-014: Eventos cronológicos da timeline de um edital';
COMMENT ON COLUMN workspace_timeline_eventos.tipo IS 'Tipo do evento: publicacao, alteracao, impugnacao, esclarecimento, resultado, homologacao, nota_manual, lembrete';
COMMENT ON COLUMN workspace_timeline_eventos.edital_id IS 'ID do edital (PNCP ou outro identificador)';
COMMENT ON COLUMN workspace_timeline_eventos.critico IS 'Se true, evento é destacado como crítico';
COMMENT ON COLUMN workspace_timeline_eventos.metadata IS 'Metadados adicionais do evento (JSON livre)';

-- B2GOPS-015: Integration channels (Slack/Teams/Email)
CREATE TABLE workspace_integracao_canais (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN ('slack','teams','email')),
    nome TEXT NOT NULL,
    url TEXT,
    email_destino TEXT,
    eventos TEXT[] DEFAULT '{}',
    ativo BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_integracao_canais_user_id ON workspace_integracao_canais(user_id);

ALTER TABLE workspace_integracao_canais ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users can view own channels" ON workspace_integracao_canais FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "Users can create own channels" ON workspace_integracao_canais FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users can delete own channels" ON workspace_integracao_canais FOR DELETE USING (auth.uid() = user_id);
CREATE POLICY "Users can update own channels" ON workspace_integracao_canais FOR UPDATE USING (auth.uid() = user_id);

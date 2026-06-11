-- CONV-011b-1: Schema post_purchase_sequences para sequência pós-compra
--
-- Rastreia o ciclo de vida pós-compra de produtos digitais one-time:
-- delivery (0h) → followup (48h) → reengagement (7d)
-- Cada registro = uma compra que disparou sequência de emails.

CREATE TABLE post_purchase_sequences (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  purchase_id UUID NOT NULL,
  product_sku TEXT NOT NULL,
  user_id UUID NOT NULL,
  stage TEXT NOT NULL DEFAULT 'delivery'
    CHECK (stage IN ('delivery', 'followup', 'reengagement', 'completed')),
  email_sent_at TIMESTAMPTZ,
  email_opened_at TIMESTAMPTZ,
  cta_clicked_at TIMESTAMPTZ,
  upsell_converted BOOLEAN DEFAULT false,
  next_sequence_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now()
);

-- Índices
CREATE INDEX idx_pps_purchase_id ON post_purchase_sequences(purchase_id);
CREATE INDEX idx_pps_user_id ON post_purchase_sequences(user_id);
CREATE INDEX idx_pps_next_sequence ON post_purchase_sequences(next_sequence_at)
  WHERE stage != 'completed';

-- Trigger para updated_at
CREATE OR REPLACE FUNCTION update_pps_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_pps_updated_at
  BEFORE UPDATE ON post_purchase_sequences
  FOR EACH ROW EXECUTE FUNCTION update_pps_updated_at();

-- RLS: usuário só vê suas próprias sequências
ALTER TABLE post_purchase_sequences ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Usuário vê suas sequências" ON post_purchase_sequences
  FOR SELECT TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "Usuário insere suas sequências" ON post_purchase_sequences
  FOR INSERT TO authenticated
  WITH CHECK (user_id = auth.uid());

-- Service role acesso total (webhook processa como service_role)
GRANT ALL ON post_purchase_sequences TO service_role;
GRANT SELECT, INSERT, UPDATE ON post_purchase_sequences TO authenticated;

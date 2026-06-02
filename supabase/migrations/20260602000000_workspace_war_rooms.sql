-- B2GOPS-004: War room tables + RPCs + SSE channel
-- Issue: #1294

-- War room (one per edital per user)
CREATE TABLE workspace_war_rooms (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  licitacao_id TEXT NOT NULL,
  licitacao_fonte TEXT NOT NULL,
  status TEXT DEFAULT 'preparacao' CHECK (status IN ('preparacao', 'em_andamento', 'concluida')),
  checklist JSONB DEFAULT '[]',
  notas_rapidas TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, licitacao_id, licitacao_fonte)
);

CREATE INDEX idx_war_rooms_user ON workspace_war_rooms(user_id);
CREATE INDEX idx_war_rooms_licitacao ON workspace_war_rooms(licitacao_id, licitacao_fonte);

-- War room members
CREATE TABLE workspace_war_room_members (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_war_room_id UUID NOT NULL REFERENCES workspace_war_rooms(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  papel TEXT NOT NULL DEFAULT 'membro' CHECK (papel IN ('lider', 'documentacao', 'lances', 'juridico', 'observador', 'membro')),
  ativo BOOLEAN DEFAULT true,
  joined_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(workspace_war_room_id, user_id)
);

CREATE INDEX idx_war_room_members_room ON workspace_war_room_members(workspace_war_room_id);
CREATE INDEX idx_war_room_members_user ON workspace_war_room_members(user_id);

-- War room action log
CREATE TABLE workspace_war_room_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  war_room_id UUID NOT NULL REFERENCES workspace_war_rooms(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  acao TEXT NOT NULL CHECK (acao IN ('checklist_toggle', 'nota_adicionada', 'membro_adicionado', 'membro_removido', 'status_change', 'documento_adicionado')),
  descricao TEXT NOT NULL,
  metadados JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_war_room_log_room ON workspace_war_room_log(war_room_id);
CREATE INDEX idx_war_room_log_created ON workspace_war_room_log(war_room_id, created_at DESC);

-- RLS: war rooms
ALTER TABLE workspace_war_rooms ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Owner can CRUD war room" ON workspace_war_rooms
  FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Members can view war room" ON workspace_war_rooms
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM workspace_war_room_members m
      WHERE m.workspace_war_room_id = id
        AND m.user_id = auth.uid()
        AND m.ativo = true
    )
  );

-- RLS: members
ALTER TABLE workspace_war_room_members ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Room owner can manage members" ON workspace_war_room_members
  FOR ALL USING (
    EXISTS (
      SELECT 1 FROM workspace_war_rooms r
      WHERE r.id = workspace_war_room_id AND r.user_id = auth.uid()
    )
  );

CREATE POLICY "Members can view member list" ON workspace_war_room_members
  FOR SELECT USING (
    EXISTS (
      SELECT 1 FROM workspace_war_room_members m
      WHERE m.workspace_war_room_id = workspace_war_room_id
        AND m.user_id = auth.uid()
        AND m.ativo = true
    )
  );

-- RLS: log
ALTER TABLE workspace_war_room_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Room participants can view log" ON workspace_war_room_log
  FOR SELECT USING (
    auth.uid() = user_id
    OR EXISTS (
      SELECT 1 FROM workspace_war_room_members m
      WHERE m.workspace_war_room_id = war_room_id
        AND m.user_id = auth.uid()
        AND m.ativo = true
    )
    OR EXISTS (
      SELECT 1 FROM workspace_war_rooms r
      WHERE r.id = war_room_id AND r.user_id = auth.uid()
    )
  );

CREATE POLICY "Room participants can insert log" ON workspace_war_room_log
  FOR INSERT WITH CHECK (
    auth.uid() = user_id
    AND (
      EXISTS (
        SELECT 1 FROM workspace_war_room_members m
        WHERE m.workspace_war_room_id = war_room_id
          AND m.user_id = auth.uid()
          AND m.ativo = true
      )
      OR EXISTS (
        SELECT 1 FROM workspace_war_rooms r
        WHERE r.id = war_room_id AND r.user_id = auth.uid()
      )
    )
  );

-- RPC: Create war room
CREATE OR REPLACE FUNCTION ops_create_war_room(
  p_licitacao_id TEXT,
  p_licitacao_fonte TEXT
)
RETURNS workspace_war_rooms
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_room workspace_war_rooms;
BEGIN
  INSERT INTO workspace_war_rooms (user_id, licitacao_id, licitacao_fonte)
  VALUES (auth.uid(), p_licitacao_id, p_licitacao_fonte)
  ON CONFLICT (user_id, licitacao_id, licitacao_fonte) DO UPDATE
    SET updated_at = now()
  RETURNING * INTO v_room;

  -- Auto-add creator as lider
  INSERT INTO workspace_war_room_members (workspace_war_room_id, user_id, papel)
  VALUES (v_room.id, auth.uid(), 'lider')
  ON CONFLICT (workspace_war_room_id, user_id) DO NOTHING;

  RETURN v_room;
END;
$$;

-- RPC: Add member to war room
CREATE OR REPLACE FUNCTION ops_add_war_room_member(
  p_war_room_id UUID,
  p_user_id UUID,
  p_papel TEXT DEFAULT 'membro'
)
RETURNS workspace_war_room_members
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_member workspace_war_room_members;
BEGIN
  -- Only room owner (or lider) can add members
  IF NOT EXISTS (
    SELECT 1 FROM workspace_war_rooms r
    WHERE r.id = p_war_room_id AND r.user_id = auth.uid()
  ) AND NOT EXISTS (
    SELECT 1 FROM workspace_war_room_members m
    WHERE m.workspace_war_room_id = p_war_room_id
      AND m.user_id = auth.uid()
      AND m.papel = 'lider'
      AND m.ativo = true
  ) THEN
    RAISE EXCEPTION 'Only room owner or lider can add members';
  END IF;

  INSERT INTO workspace_war_room_members (workspace_war_room_id, user_id, papel)
  VALUES (p_war_room_id, p_user_id, p_papel)
  ON CONFLICT (workspace_war_room_id, user_id) DO UPDATE
    SET papel = p_papel, ativo = true
  RETURNING * INTO v_member;

  -- Log the action
  INSERT INTO workspace_war_room_log (war_room_id, user_id, acao, descricao, metadados)
  VALUES (p_war_room_id, auth.uid(), 'membro_adicionado',
          'Membro adicionado com papel ' || p_papel,
          jsonb_build_object('member_user_id', p_user_id, 'papel', p_papel));

  RETURN v_member;
END;
$$;

-- RPC: Log war room action (for SSE broadcast)
CREATE OR REPLACE FUNCTION ops_log_war_room_action(
  p_war_room_id UUID,
  p_acao TEXT,
  p_descricao TEXT,
  p_metadados JSONB DEFAULT '{}'
)
RETURNS workspace_war_room_log
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_log workspace_war_room_log;
BEGIN
  INSERT INTO workspace_war_room_log (war_room_id, user_id, acao, descricao, metadados)
  VALUES (p_war_room_id, auth.uid(), p_acao, p_descricao, p_metadados)
  RETURNING * INTO v_log;

  -- Notify SSE channel for real-time collaboration
  PERFORM pg_notify('war_room_' || p_war_room_id::text,
    jsonb_build_object(
      'type', 'war_room_action',
      'action', p_acao,
      'description', p_descricao,
      'user_id', auth.uid(),
      'metadata', p_metadados,
      'timestamp', now()
    )::text
  );

  RETURN v_log;
END;
$$;

-- RPC: Get war room by licitacao
CREATE OR REPLACE FUNCTION ops_get_war_room(
  p_licitacao_id TEXT,
  p_licitacao_fonte TEXT
)
RETURNS SETOF workspace_war_rooms
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
  SELECT * FROM workspace_war_rooms
  WHERE licitacao_id = p_licitacao_id
    AND licitacao_fonte = p_licitacao_fonte
    AND (
      user_id = auth.uid()
      OR EXISTS (
        SELECT 1 FROM workspace_war_room_members m
        WHERE m.workspace_war_room_id = id
          AND m.user_id = auth.uid()
          AND m.ativo = true
      )
    );
$$;

-- RPC: Toggle checklist item
CREATE OR REPLACE FUNCTION ops_toggle_checklist_item(
  p_war_room_id UUID,
  p_item_id TEXT,
  p_concluido BOOLEAN
)
RETURNS workspace_war_rooms
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
DECLARE
  v_room workspace_war_rooms;
  v_item_text TEXT;
  v_checklist JSONB;
  v_item JSONB;
  v_idx INT;
BEGIN
  SELECT * INTO v_room FROM workspace_war_rooms WHERE id = p_war_room_id;

  -- Find and update the checklist item
  v_checklist := v_room.checklist;
  FOR v_idx IN 0..jsonb_array_length(v_checklist) - 1 LOOP
    v_item := v_checklist->v_idx;
    IF v_item->>'id' = p_item_id THEN
      v_item_text := v_item->>'texto';
      v_checklist := jsonb_set(v_checklist, ARRAY[v_idx::text, 'concluido'], to_jsonb(p_concluido));
      v_checklist := jsonb_set(v_checklist, ARRAY[v_idx::text, 'data_conclusao'],
        CASE WHEN p_concluido THEN to_jsonb(now()::text) ELSE 'null'::jsonb END);
      EXIT;
    END IF;
  END LOOP;

  UPDATE workspace_war_rooms
  SET checklist = v_checklist, updated_at = now()
  WHERE id = p_war_room_id
  RETURNING * INTO v_room;

  -- Log action
  INSERT INTO workspace_war_room_log (war_room_id, user_id, acao, descricao, metadados)
  VALUES (p_war_room_id, auth.uid(), 'checklist_toggle',
    CASE WHEN p_concluido THEN 'Marcou "' || v_item_text || '" como concluído'
         ELSE 'Desmarcou "' || v_item_text || '"' END,
    jsonb_build_object('checklist_item_id', p_item_id, 'concluido', p_concluido));

  RETURN v_room;
END;
$$;

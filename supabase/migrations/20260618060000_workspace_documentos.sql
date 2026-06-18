-- ============================================================================
-- UP: B2GOPS-013 (#2023) — Documentos colaborativos + templates
-- Date: 2026-06-18
-- Author: @dev
-- ============================================================================
-- Creates workspace_documento_templates (seed: 6 built-in templates) and
-- workspace_documentos (user documents CRUD).
-- ============================================================================

-- ---------------------------------------------------------------------------
-- 1. workspace_documento_templates — read-only templates seeded below
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workspace_documento_templates (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL CHECK (tipo IN ('proposta','declaracao','recurso','impugnacao','carta','planilha')),
    conteudo TEXT NOT NULL,
    descricao TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE workspace_documento_templates ENABLE ROW LEVEL SECURITY;

CREATE POLICY "templates_select_all"
    ON workspace_documento_templates
    FOR SELECT
    USING (auth.role() = 'authenticated');

-- ---------------------------------------------------------------------------
-- 2. workspace_documentos — user-owned documents
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS workspace_documentos (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    edital_id TEXT,
    template_id UUID REFERENCES workspace_documento_templates(id) ON DELETE SET NULL,
    titulo TEXT NOT NULL,
    conteudo TEXT NOT NULL DEFAULT '',
    tipo TEXT NOT NULL CHECK (tipo IN ('proposta','declaracao','recurso','impugnacao','carta','planilha')),
    variaveis JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_documentos_user_id ON workspace_documentos(user_id);
CREATE INDEX IF NOT EXISTS idx_documentos_tipo ON workspace_documentos(tipo);

ALTER TABLE workspace_documentos ENABLE ROW LEVEL SECURITY;

CREATE POLICY "docs_select_own"
    ON workspace_documentos
    FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "docs_insert_own"
    ON workspace_documentos
    FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "docs_update_own"
    ON workspace_documentos
    FOR UPDATE
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "docs_delete_own"
    ON workspace_documentos
    FOR DELETE
    USING (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- 3. Seed: 6 built-in templates
-- ---------------------------------------------------------------------------
INSERT INTO workspace_documento_templates (nome, tipo, descricao, conteudo) VALUES
('Proposta Comercial', 'proposta', 'Modelo de proposta comercial para participacao em licitacao',
 '# PROPOSTA COMERCIAL

A {{orgao}}
Referente ao edital: {{objeto}}
Modalidade: {{modalidade}}

## 1. IDENTIFICACAO DA PROPONENTE
{{empresa}}, CNPJ {{cnpj}}, apresenta sua proposta comercial para o objeto acima.

## 2. VALOR DA PROPOSTA
R$ {{valor}}

## 3. VALIDADE DA PROPOSTA
60 dias a partir da data de abertura: {{data_abertura}}

## 4. CONDICOES GERAIS
- Prazo de entrega: conforme cronograma do edital
- Garantia: conforme exigido no instrumento convocatorio
- Condicoes de pagamento: conforme estabelecido no contrato
'),
('Declaracao de Habilitacao', 'declaracao', 'Declaracao de atendimento aos requisitos de habilitacao',
 '# DECLARACAO DE HABILITACAO

{{empresa}}, CNPJ {{cnpj}}, declara para os devidos fins que atende a todos os requisitos de habilitacao exigidos no edital referente ao objeto {{objeto}}, do orgao {{orgao}}.

Declara ainda que:
- Nao possui restricoes junto ao CADIN
- Nao possui registro no SICAF que a impeca de contratar com a Administracao
- Apresenta documentacao fiscal regular
- Atende as condicoes de qualificacao tecnica exigidas

{{uf}}, {{data_abertura}}
'),
('Recurso Administrativo', 'recurso', 'Modelo de recurso administrativo contra decisao',
 '# RECURSO ADMINISTRATIVO

A {{orgao}}
Ref: Edital {{objeto}} — Modalidade {{modalidade}}

{{empresa}}, CNPJ {{cnpj}}, vem respeitosamente interpor RECURSO ADMINISTRATIVO contra a decisao proferida nos autos do procedimento licitatorio em epigrafe, pelos motivos de fato e de direito a seguir expostos.

## I - DOS FATOS
[Descrever os fatos que motivam o recurso]

## II - DO DIREITO
[Fundamentacao juridica do recurso]

## III - DO PEDIDO
Ante o exposto, requer o conhecimento e provimento do presente recurso para [especificar o pedido].

Nestes termos, pede deferimento.
{{uf}}, {{data_abertura}}
'),
('Impugnacao de Edital', 'impugnacao', 'Modelo de impugnacao de edital',
 '# IMPUGNACAO DE EDITAL

Ao(A) {{orgao}}
Referencia: Edital {{objeto}} — Modalidade {{modalidade}}

{{empresa}}, CNPJ {{cnpj}}, vem IMPUGNAR o edital acima identificado, com fundamento no art. 41, § 1o, da Lei no 8.666/93, pelas razoes a seguir expostas.

## I - DOS PONTOS IMPUGNADOS
[Especificar os itens do edital que estao sendo impugnados]

## II - DAS RAZOES DA IMPUGNACAO
[Expor as razoes juridicas e tecnicas]

## III - DO PEDIDO
Requere-se o acolhimento da presente impugnacao para que sejam retificados os pontos apontados.

Nestes termos, pede deferimento.
{{uf}}, {{data_abertura}}
'),
('Carta de Apresentacao', 'carta', 'Carta de apresentacao da empresa',
 '# CARTA DE APRESENTACAO

A {{orgao}}
A/C Comissao de Licitacao

{{empresa}}, CNPJ {{cnpj}}, apresenta seus documentos para participacao no edital {{objeto}}, Modalidade {{modalidade}}, conforme documentacao anexa.

Atenciosamente,
{{empresa}}
'),
('Planilha de Precos', 'planilha', 'Planilha de precos e composicao de custos',
 '# PLANILHA DE PRECOS

Edital: {{objeto}}
Orgao: {{orgao}}
Data: {{data_abertura}}

## Itens

| Item | Descricao | Unidade | Quantidade | Valor Unitario | Valor Total |
|------|-----------|---------|------------|----------------|-------------|
| 1 | | | | R$ | R$ |
| 2 | | | | R$ | R$ |
| 3 | | | | R$ | R$ |
| 4 | | | | R$ | R$ |
| 5 | | | | R$ | R$ |
| **TOTAL** | | | | | **R$ {{valor}}** |

## Observacoes
- Todos os precos incluem tributos, encargos sociais e demais custos incidentes
- Validade da proposta: 60 dias
');

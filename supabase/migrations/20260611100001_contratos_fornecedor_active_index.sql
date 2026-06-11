-- ISSUE-1650: Partial composite index on (ni_fornecedor, data_assinatura DESC)
-- WHERE is_active for pncp_supplier_contracts.
--
-- Contexto: /v1/fornecedores/{cnpj}/profile query:
--   SELECT ... FROM pncp_supplier_contracts
--   WHERE ni_fornecedor = <cnpj> AND is_active = TRUE
--   ORDER BY data_assinatura DESC LIMIT 500
--
-- O indice existente idx_psc_fornecedor_data (ni_fornecedor, data_assinatura
-- DESC) nao inclui is_active, forçando filtro extra apos index scan. Para
-- fornecedores com muitos contratos (ex: 03130891000199 observado 8862ms),
-- isso adiciona latency significativa.
--
-- Este indice parcial (WHERE is_active = TRUE) elimina o filtro extra e
-- reduz o tamanho do indice (~60% dos contratos sao ativos).
-- CONCURRENTLY: nao bloqueia writes durante criacao.

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_psc_fornecedor_active_data
    ON public.pncp_supplier_contracts (ni_fornecedor, data_assinatura DESC)
    WHERE is_active = TRUE;

COMMENT ON INDEX public.idx_psc_fornecedor_active_data IS
    'ISSUE-1650: partial composite index for fornecedor_profile queries. Covers ni_fornecedor + is_active + data_assinatura ORDER in a single index scan.';

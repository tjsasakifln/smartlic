CREATE INDEX IF NOT EXISTS idx_pncp_raw_bids_codigo_municipio_ibge
    ON public.pncp_raw_bids (codigo_municipio_ibge)
    WHERE is_active;

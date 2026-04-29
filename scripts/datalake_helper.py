"""DataLake Supabase shared helper.

Centraliza acesso ao DataLake (`pncp_raw_bids`, `pncp_supplier_contracts`,
`enriched_entities`) para os commands B2G (`/intel-busca`, `/pricing-b2g`,
`/intel-b2g`, `/retention-b2g`, `/radar-b2g`, etc.).

Pattern espelha `scripts/intel-collect.py:575-720` (referência original):
- Flag `DATALAKE_QUERY_ENABLED=true` ativa o cliente
- Override `--no-datalake` no caller força fallback live
- Fallback gracioso: nunca bloqueia execução; retorna `(None, error_meta)` ou
  `[]` em caso de falha (env vars ausentes, supabase-py não instalado, RPC erro)

Uso típico:

    from datalake_helper import DatalakeClient

    dl = DatalakeClient()
    if dl.is_enabled:
        rows, meta = dl.search_bids(ufs=["SP"], dias=30, modalidades=[5, 6])
        if rows is None:
            # falha — usar fluxo live
            ...
        else:
            for row in rows:
                ...
"""

from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from typing import Any


_DEFAULT_LIMIT = 2000
_MAX_LIMIT = 5000  # search_datalake RPC cap


class DatalakeClient:
    """Wrapper sobre Supabase RPCs e tabelas do DataLake PNCP."""

    def __init__(self) -> None:
        self._sb: Any = None
        self._init_error: str | None = None
        self._enabled: bool | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    @property
    def is_enabled(self) -> bool:
        """True quando DATALAKE_QUERY_ENABLED=true E env vars OK E supabase-py disponível."""
        if self._enabled is not None:
            return self._enabled
        if os.getenv("DATALAKE_QUERY_ENABLED", "").lower() not in ("true", "1"):
            self._enabled = False
            return False
        if not os.getenv("SUPABASE_URL") or not (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
        ):
            self._init_error = "SUPABASE_URL or key not configured"
            self._enabled = False
            return False
        try:
            import supabase  # noqa: F401
        except ImportError:
            self._init_error = "supabase-py not installed"
            self._enabled = False
            return False
        self._enabled = True
        return True

    def _client(self) -> Any:
        """Lazy init Supabase client."""
        if self._sb is not None:
            return self._sb
        if not self.is_enabled:
            return None
        try:
            from supabase import create_client

            url = os.getenv("SUPABASE_URL", "")
            key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "") or os.getenv(
                "SUPABASE_ANON_KEY", ""
            )
            self._sb = create_client(url, key)
        except Exception as e:
            self._init_error = f"Supabase client init failed: {e}"
            self._sb = None
        return self._sb

    @property
    def init_error(self) -> str | None:
        return self._init_error

    # ------------------------------------------------------------------
    # search_datalake RPC (pncp_raw_bids)
    # ------------------------------------------------------------------

    def search_bids(
        self,
        ufs: list[str] | None = None,
        dias: int | None = None,
        date_start: date | str | None = None,
        date_end: date | str | None = None,
        tsquery: str | None = None,
        websearch_text: str | None = None,
        modalidades: list[int] | None = None,
        valor_min: float | None = None,
        valor_max: float | None = None,
        esferas: list[str] | None = None,
        modo: str = "publicacao",
        limit: int = _DEFAULT_LIMIT,
        paginate_by_uf_modalidade: bool = True,
        verbose: bool = False,
    ) -> tuple[list[dict] | None, dict]:
        """Wrapper sobre `search_datalake` RPC.

        Args:
            ufs: lista de siglas UF (ou None p/ todas)
            dias: janela [hoje - dias, hoje]; ignorado se date_start/date_end fornecidos
            date_start, date_end: bounds explícitos (ISO YYYY-MM-DD ou date)
            tsquery: tsquery PT-BR (sector keywords OR-joined)
            websearch_text: texto livre user (phrases + exclusions)
            modalidades: lista de modalidade_id (4=Concorrência, 5/6=Pregão, 8=Inexigib...)
            valor_min, valor_max: range de valor_total_estimado
            esferas: ["F","E","M","D"]
            modo: 'publicacao' (filtra por data_publicacao) ou 'abertas' (encerramento futuro)
            limit: cap por chamada (max 5000)
            paginate_by_uf_modalidade: se True, faz N×M chamadas para evitar PostgREST 1000-row cap

        Returns:
            (rows, meta) onde rows é lista de dicts ou None em falha. Meta inclui
            `source='datalake'`, `total_raw`, `pages_fetched`, e `errors`.
        """
        if not self.is_enabled:
            return None, {"datalake_error": self._init_error or "disabled"}

        sb = self._client()
        if sb is None:
            return None, {"datalake_error": self._init_error or "client unavailable"}

        ds, de = self._resolve_dates(dias, date_start, date_end)

        base_params: dict[str, Any] = {
            "p_ufs": ufs or None,
            "p_date_start": ds,
            "p_date_end": de,
            "p_modalidades": modalidades or None,
            "p_modo": modo,
            "p_limit": min(limit, _MAX_LIMIT),
        }
        if tsquery is not None:
            base_params["p_tsquery"] = tsquery
        if websearch_text is not None:
            base_params["p_websearch_text"] = websearch_text
        if valor_min is not None:
            base_params["p_valor_min"] = valor_min
        if valor_max is not None:
            base_params["p_valor_max"] = valor_max
        if esferas:
            base_params["p_esferas"] = esferas

        rows: list[dict] = []
        errors: list[str] = []
        pages = 0

        if paginate_by_uf_modalidade and ufs and modalidades:
            # PostgREST cap = 1000 rows; paginar por (UF, modalidade)
            for uf in ufs:
                uf_total = 0
                for mod_id in modalidades:
                    p = {**base_params, "p_ufs": [uf], "p_modalidades": [mod_id]}
                    try:
                        r = sb.rpc("search_datalake", p).execute()
                        chunk = r.data or []
                        rows.extend(chunk)
                        uf_total += len(chunk)
                        pages += 1
                    except Exception as e:
                        errors.append(f"{uf}/mod{mod_id}: {e}")
                if verbose and uf_total:
                    print(f"      {uf}: {uf_total} editais")
        else:
            try:
                r = sb.rpc("search_datalake", base_params).execute()
                rows = r.data or []
                pages = 1
            except Exception as e:
                errors.append(str(e))

        meta = {
            "source": "datalake",
            "total_raw": len(rows),
            "pages_fetched": pages,
            "errors": errors,
            "date_start": ds,
            "date_end": de,
        }

        if not rows and errors:
            return None, {**meta, "datalake_error": errors[0]}

        return rows, meta

    def search_bids_trigram(
        self,
        query_term: str,
        ufs: list[str] | None = None,
        limit: int = 200,
    ) -> tuple[list[dict] | None, dict]:
        """Fuzzy fallback (`search_datalake_trigram_fallback`). Use quando FTS retorna 0."""
        if not self.is_enabled:
            return None, {"datalake_error": self._init_error or "disabled"}
        sb = self._client()
        if sb is None:
            return None, {"datalake_error": self._init_error or "client unavailable"}
        try:
            r = sb.rpc(
                "search_datalake_trigram_fallback",
                {"p_query_term": query_term, "p_ufs": ufs, "p_limit": min(limit, 500)},
            ).execute()
            rows = r.data or []
            return rows, {"source": "datalake_trigram", "total_raw": len(rows)}
        except Exception as e:
            return None, {"datalake_error": f"trigram failed: {e}"}

    # ------------------------------------------------------------------
    # pncp_supplier_contracts (raw SELECT)
    # ------------------------------------------------------------------

    def supplier_contracts(
        self,
        ni_fornecedor: str | None = None,
        orgao_cnpj: str | None = None,
        ufs: list[str] | None = None,
        keywords: list[str] | None = None,
        date_start: date | str | None = None,
        date_end: date | str | None = None,
        meses: int | None = None,
        modalidade_keywords: list[str] | None = None,
        limit: int = 1000,
        order_by_data_desc: bool = True,
    ) -> tuple[list[dict] | None, dict]:
        """SELECT em `pncp_supplier_contracts` com filtros compostos.

        Args:
            ni_fornecedor: CNPJ 14d do fornecedor (lookup O(1) via idx_psc_ni_fornecedor)
            orgao_cnpj: CNPJ 14d do órgão comprador
            ufs: lista de UFs
            keywords: lista de termos para ILIKE em objeto_contrato (OR)
            date_start, date_end: bounds em data_assinatura
            meses: alternativa — janela [hoje - meses, hoje]
            modalidade_keywords: NÃO disponível (tabela não tem modalidade — ignored)
            limit: cap por chamada (PostgREST max 1000 default)
            order_by_data_desc: True (default) ordena por data_assinatura DESC

        Returns:
            (rows, meta) ou (None, error_meta).
        """
        if not self.is_enabled:
            return None, {"datalake_error": self._init_error or "disabled"}
        sb = self._client()
        if sb is None:
            return None, {"datalake_error": self._init_error or "client unavailable"}

        ds, de = self._resolve_dates(meses_to_dias(meses), date_start, date_end)

        try:
            q = sb.table("pncp_supplier_contracts").select(
                "numero_controle_pncp,ni_fornecedor,nome_fornecedor,orgao_cnpj,"
                "orgao_nome,uf,municipio,esfera,valor_global,data_assinatura,"
                "objeto_contrato,ingested_at"
            ).eq("is_active", True)
            if ni_fornecedor:
                q = q.eq("ni_fornecedor", "".join(ch for ch in ni_fornecedor if ch.isdigit()))
            if orgao_cnpj:
                q = q.eq("orgao_cnpj", "".join(ch for ch in orgao_cnpj if ch.isdigit()))
            if ufs:
                q = q.in_("uf", [u.upper() for u in ufs])
            if ds:
                q = q.gte("data_assinatura", ds)
            if de:
                q = q.lte("data_assinatura", de)
            if keywords:
                # AND ILIKE chain — todos os tokens devem aparecer no objeto.
                # Pricing exige matching restritivo: "limpeza hospitalar" deve casar
                # contratos contendo AMBAS as palavras, não qualquer uma. OR resultava
                # em mediana enviesada por contratos genéricos (ex: "produtos de limpeza"
                # R$300 misturado com "limpeza hospitalar" R$200k).
                for k in keywords:
                    if k:
                        q = q.ilike("objeto_contrato", f"%{k.lower()}%")
            if order_by_data_desc:
                q = q.order("data_assinatura", desc=True)
            q = q.limit(min(limit, 1000))
            r = q.execute()
            rows = r.data or []
            return rows, {"source": "datalake_contracts", "total": len(rows)}
        except Exception as e:
            return None, {"datalake_error": f"supplier_contracts query failed: {e}"}

    def pricing_stats(
        self,
        keywords: list[str],
        ufs: list[str] | None = None,
        meses: int = 12,
        orgao_cnpj: str | None = None,
        valor_min: float = 1.0,
    ) -> tuple[dict | None, dict]:
        """Estatísticas agregadas de preço sobre `pncp_supplier_contracts`.

        Args:
            keywords: termos (ILIKE OR) para `objeto_contrato`
            ufs: filtro de UF (opcional)
            meses: janela em data_assinatura
            orgao_cnpj: filtro adicional por órgão
            valor_min: piso para descartar registros zerados (default 1.0)

        Returns:
            ({n, p10, p25, mediana, p75, p90, media, dp, cv, sample}, meta)
            onde `sample` são os top-N contratos brutos (ordenados por data desc, max 200).
        """
        rows, meta = self.supplier_contracts(
            keywords=keywords,
            ufs=ufs,
            meses=meses,
            orgao_cnpj=orgao_cnpj,
            limit=1000,
        )
        if rows is None:
            return None, meta

        valid = [
            r for r in rows
            if r.get("valor_global") is not None and float(r["valor_global"]) >= valor_min
        ]
        if not valid:
            return None, {**meta, "datalake_error": "0 contracts with valid valor_global"}

        valores = sorted(float(r["valor_global"]) for r in valid)
        n = len(valores)
        media = sum(valores) / n
        var = sum((v - media) ** 2 for v in valores) / n
        dp = var ** 0.5
        cv = (dp / media * 100) if media > 0 else 0.0

        def percentile(p: float) -> float:
            if n == 1:
                return valores[0]
            k = (n - 1) * p
            f = int(k)
            c = min(f + 1, n - 1)
            if f == c:
                return valores[f]
            return valores[f] + (valores[c] - valores[f]) * (k - f)

        stats = {
            "n": n,
            "p10": round(percentile(0.10), 2),
            "p25": round(percentile(0.25), 2),
            "mediana": round(percentile(0.50), 2),
            "p75": round(percentile(0.75), 2),
            "p90": round(percentile(0.90), 2),
            "media": round(media, 2),
            "dp": round(dp, 2),
            "cv": round(cv, 2),
            "sample": valid[:200],
        }
        return stats, {**meta, "n_valid": n, "n_filtered_out": len(rows) - n}

    # ------------------------------------------------------------------
    # enriched_entities (BrasilAPI cache, TTL lógico 30d)
    # ------------------------------------------------------------------

    def enriched_entity(
        self,
        entity_type: str,
        entity_id: str,
        max_age_days: int = 30,
    ) -> tuple[dict | None, dict]:
        """Lookup em `enriched_entities`.

        Args:
            entity_type: 'fornecedor' | 'municipio' | 'orgao'
            entity_id: CNPJ 14d ou IBGE 7d
            max_age_days: rejeita rows com `enriched_at` mais velhas (default 30d)

        Returns:
            (data_payload | None, meta). data é o JSONB armazenado.
        """
        if not self.is_enabled:
            return None, {"datalake_error": self._init_error or "disabled"}
        sb = self._client()
        if sb is None:
            return None, {"datalake_error": self._init_error or "client unavailable"}
        try:
            r = (
                sb.table("enriched_entities")
                .select("data,enriched_at")
                .eq("entity_type", entity_type)
                .eq("entity_id", entity_id)
                .limit(1)
                .execute()
            )
            rows = r.data or []
            if not rows:
                return None, {"source": "enriched_cache_miss"}
            row = rows[0]
            enriched_at = row.get("enriched_at") or ""
            try:
                ts = datetime.fromisoformat(enriched_at.replace("Z", "+00:00"))
                age = datetime.now(ts.tzinfo) - ts
                if age > timedelta(days=max_age_days):
                    return None, {"source": "enriched_cache_stale", "age_days": age.days}
            except (ValueError, TypeError):
                pass
            return row.get("data"), {
                "source": "enriched_cache_hit",
                "enriched_at": enriched_at,
            }
        except Exception as e:
            return None, {"datalake_error": f"enriched_entities query failed: {e}"}

    # ------------------------------------------------------------------
    # ingestion_runs (último ETL — usado pelo radar híbrido)
    # ------------------------------------------------------------------

    def last_etl_at(self, source: str = "pncp") -> tuple[datetime | None, dict]:
        """Último ARQ run bem-sucedido em `ingestion_runs`.

        Usado pelo `/radar-b2g` modo híbrido: se `last_etl_at < NOW() - 30min`, o caller
        complementa o resultado do DataLake com 1 curl PNCP cobrindo `[last_etl_at, NOW()]`.
        """
        if not self.is_enabled:
            return None, {"datalake_error": self._init_error or "disabled"}
        sb = self._client()
        if sb is None:
            return None, {"datalake_error": self._init_error or "client unavailable"}
        try:
            r = (
                sb.table("ingestion_runs")
                .select("finished_at,started_at,status")
                .eq("source", source)
                .eq("status", "success")
                .order("finished_at", desc=True)
                .limit(1)
                .execute()
            )
            rows = r.data or []
            if not rows:
                return None, {"source": "ingestion_runs_empty"}
            ts_raw = rows[0].get("finished_at") or rows[0].get("started_at")
            if not ts_raw:
                return None, {"source": "ingestion_runs_no_timestamp"}
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            return ts, {"source": "ingestion_runs", "finished_at": ts_raw}
        except Exception as e:
            return None, {"datalake_error": f"ingestion_runs query failed: {e}"}

    # ------------------------------------------------------------------
    # Date helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_dates(
        dias: int | None,
        date_start: date | str | None,
        date_end: date | str | None,
    ) -> tuple[str | None, str | None]:
        """Normaliza inputs de data para ISO YYYY-MM-DD."""
        def to_iso(d: date | str | None) -> str | None:
            if d is None:
                return None
            if isinstance(d, str):
                return d[:10]
            return d.strftime("%Y-%m-%d")

        ds = to_iso(date_start)
        de = to_iso(date_end)
        if ds is None and de is None and dias is not None:
            today = date.today()
            ds = (today - timedelta(days=dias)).strftime("%Y-%m-%d")
            de = today.strftime("%Y-%m-%d")
        return ds, de


def meses_to_dias(meses: int | None) -> int | None:
    """Converte janela em meses para dias (~30.4 dias/mês)."""
    if meses is None:
        return None
    return int(meses * 30.4)

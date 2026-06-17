"""Pipeline helper functions — extracted from search_pipeline.py (TD-008 AC20).

Standalone utility functions for bid processing, coverage metrics,
and confidence mapping. No pipeline state or class dependencies.
"""

import logging
from datetime import datetime, timezone as _tz

from schemas import LicitacaoItem, UfStatusDetail, CoverageMetadata
from utils.value_sanitizer import VALUE_HARD_CAP

logger = logging.getLogger(__name__)


def _sanitize_item_valor(valor) -> float | None:
    """ISSUE-022: Sanitize individual bid value for card display.

    Values exceeding the hard cap (R$ 10B) are returned as None
    so frontend shows "Valor não informado" instead of absurd numbers.
    """
    if valor is None:
        return None
    try:
        v = float(valor)
    except (ValueError, TypeError):
        return None
    if v <= 0:
        return None
    if v > VALUE_HARD_CAP:
        return None
    return v


def _build_pncp_link(lic: dict) -> str | None:
    """Build PNCP link from bid data.

    Priority: constructed PNCP URL from numeroControlePNCP >
    cnpjOrgao/anoCompra/sequencialCompra > linkSistemaOrigem >
    linkProcessoEletronico.

    HOTFIX 2026-06-17: PNCP API's linkSistemaOrigem points to ComprasNet
    (cnetmobile.estaleiro.serpro.gov.br), NOT pncp.gov.br. ComprasNet links
    often fail or require auth. We now prioritize constructing the PNCP URL
    from structured fields, falling back to linkSistemaOrigem only when
    we cannot build a PNCP URL.

    Returns None when no link can be constructed.
    """
    link = None

    # Priority 1: Construct PNCP URL from numeroControlePNCP
    numero_controle = lic.get("numeroControlePNCP", "")
    if numero_controle:
        try:
            partes = numero_controle.split("/")
            if len(partes) == 2:
                ano = partes[1]
                cnpj_tipo_seq = partes[0].split("-")
                if len(cnpj_tipo_seq) >= 3:
                    cnpj = cnpj_tipo_seq[0]
                    sequencial = cnpj_tipo_seq[2].lstrip("0")
                    if cnpj and ano and sequencial:
                        link = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{sequencial}"
        except Exception as e:
            logger.debug(f"PNCP link extraction failed for {numero_controle}: {e}")

    # Priority 2: Construct PNCP URL from cnpjOrgao/anoCompra/sequencialCompra
    if not link:
        cnpj = lic.get("cnpjOrgao", "")
        ano = lic.get("anoCompra", "")
        seq = lic.get("sequencialCompra", "")
        if cnpj and ano and seq:
            link = f"https://pncp.gov.br/app/editais/{cnpj}/{ano}/{seq}"

    # Priority 3: Fallback to linkSistemaOrigem (may point to ComprasNet or other sources)
    if not link:
        link = lic.get("linkSistemaOrigem")

    # Priority 4: Fallback to linkProcessoEletronico
    if not link:
        link = lic.get("linkProcessoEletronico")

    return link or None


def _calcular_urgencia(dias_restantes: int | None) -> str | None:
    """Classify urgency based on days remaining until deadline."""
    if dias_restantes is None:
        return None
    if dias_restantes < 0:
        return "encerrada"
    if dias_restantes < 7:
        return "critica"
    if dias_restantes < 14:
        return "alta"
    if dias_restantes <= 30:
        return "media"
    return "baixa"


def _calcular_dias_restantes(data_encerramento_str: str | None) -> int | None:
    """Calculate days remaining from today to the deadline date."""
    if not data_encerramento_str:
        return None
    try:
        from datetime import date
        enc = date.fromisoformat(data_encerramento_str[:10])
        return (enc - date.today()).days
    except (ValueError, TypeError):
        return None


def _map_confidence(relevance_source: str | None) -> str | None:
    """Map relevance_source to categorical confidence level."""
    if not relevance_source:
        return None
    mapping = {
        "keyword": "high",
        "keyword_peripheral": "low",  # ISSUE-029: keyword match but not primary sector
        "llm_standard": "medium",
        "llm_conservative": "low",
        "llm_zero_match": "low",
        # ISSUE-044: sources that indicate no keyword validation occurred
        "sector_relaxation": "low",
        "unfiltered": "low",
        "substring_relaxation": "low",
    }
    return mapping.get(relevance_source)


def _convert_to_licitacao_items(licitacoes: list[dict]) -> list[LicitacaoItem]:
    """Convert raw bid dictionaries to LicitacaoItem objects for frontend display."""
    items = []
    for lic in licitacoes:
        try:
            data_enc = lic.get("dataEncerramentoProposta", "")[:10] if lic.get("dataEncerramentoProposta") else None
            dias_rest = _calcular_dias_restantes(data_enc)
            item = LicitacaoItem(
                pncp_id=lic.get("codigoCompra", lic.get("numeroControlePNCP", "")),
                objeto=lic.get("objetoCompra", "")[:500],
                orgao=lic.get("nomeOrgao", ""),
                uf=lic.get("uf", ""),
                municipio=lic.get("municipio"),
                valor=_sanitize_item_valor(lic.get("valorTotalEstimado")),
                modalidade=lic.get("modalidadeNome"),
                data_publicacao=lic.get("dataPublicacaoPncp", "")[:10] if lic.get("dataPublicacaoPncp") else None,
                data_abertura=lic.get("dataAberturaProposta", "")[:10] if lic.get("dataAberturaProposta") else None,
                data_encerramento=data_enc,
                dias_restantes=dias_rest,
                urgencia=_calcular_urgencia(dias_rest),
                link=_build_pncp_link(lic),
                numero_compra=lic.get("numeroEdital") or lic.get("codigoCompra") or None,
                cnpj_orgao=lic.get("cnpjOrgao") or None,
                source=lic.get("_source"),
                relevance_score=lic.get("_relevance_score"),
                matched_terms=lic.get("_matched_terms"),
                relevance_source=lic.get("_relevance_source"),
                confidence_score=lic.get("_confidence_score"),
                llm_evidence=lic.get("_llm_evidence"),
                confidence=_map_confidence(lic.get("_relevance_source")),
                viability_score=lic.get("_viability_score"),
                viability_level=lic.get("_viability_level"),
                viability_factors=lic.get("_viability_factors"),
                value_source=lic.get("_value_source"),
            )
            items.append(item)
        except Exception as e:
            logger.error(f"Failed to convert bid to LicitacaoItem: {e}")
            import sentry_sdk
            sentry_sdk.capture_exception(e)
            from metrics import ITEMS_CONVERSION_ERRORS
            ITEMS_CONVERSION_ERRORS.inc()
            continue
    return items


def _build_coverage_metrics(ctx) -> tuple[int, list[UfStatusDetail]]:
    """Build coverage_pct and ufs_status_detail from search context."""
    requested_ufs = list(ctx.request.ufs)
    total_requested = len(requested_ufs)
    if total_requested == 0:
        return 100, []

    failed_set = set(ctx.failed_ufs or [])
    uf_counts: dict[str, int] = {}
    for lic in ctx.licitacoes_raw:
        uf = lic.get("uf", "")
        if uf:
            uf_counts[uf] = uf_counts.get(uf, 0) + 1

    details: list[UfStatusDetail] = []
    succeeded_count = 0
    for uf in requested_ufs:
        if uf in failed_set:
            details.append(UfStatusDetail(uf=uf, status="timeout", results_count=0))
        else:
            succeeded_count += 1
            details.append(UfStatusDetail(uf=uf, status="ok", results_count=uf_counts.get(uf, 0)))

    coverage_pct = int((succeeded_count / total_requested) * 100)
    return coverage_pct, details


def _build_coverage_metadata(ctx) -> CoverageMetadata:
    """Build consolidated CoverageMetadata from search context."""
    requested = list(ctx.request.ufs)
    processed = list(ctx.succeeded_ufs or [])
    failed = list(ctx.failed_ufs or [])
    total = len(requested)
    coverage = round(len(processed) / total * 100, 1) if total > 0 else 0.0

    if ctx.response_state == "live" or (not ctx.cached and ctx.response_state != "cached"):
        freshness = "live"
    elif ctx.cache_status == "fresh":
        freshness = "cached_fresh"
    else:
        freshness = "cached_stale"

    if ctx.cached and ctx.cached_at:
        data_timestamp = ctx.cached_at
    else:
        data_timestamp = datetime.now(_tz.utc).isoformat()

    # ISSUE-073: Calculate per-UF result counts from filtered results
    uf_result_counts: dict[str, int] = {}
    _filtered = getattr(ctx, "licitacoes_filtradas", None)
    _raw = getattr(ctx, "licitacoes_raw", None)
    items = _filtered if isinstance(_filtered, list) else (_raw if isinstance(_raw, list) else [])
    for lic in items:
        uf = (lic.get("uf") or "").upper()
        if uf:
            uf_result_counts[uf] = uf_result_counts.get(uf, 0) + 1
    ufs_empty = [uf for uf in processed if uf_result_counts.get(uf, 0) == 0]

    return CoverageMetadata(
        ufs_requested=requested,
        ufs_processed=processed,
        ufs_failed=failed,
        ufs_empty=ufs_empty,
        uf_result_counts=uf_result_counts,
        coverage_pct=coverage,
        data_timestamp=data_timestamp,
        freshness=freshness,
    )


def _maybe_send_quota_email(user_id: str, quota_used: int, quota_info) -> None:
    """Send quota warning/exhaustion email if threshold reached. Fire-and-forget."""
    try:
        max_quota = quota_info.capabilities.get("max_requests_per_month", 0)
        if max_quota <= 0:
            return

        pct = quota_used / max_quota
        reset_date = quota_info.quota_reset_date.strftime("%d/%m/%Y")

        from supabase_client import get_supabase
        sb = get_supabase()
        profile = sb.table("profiles").select("email, full_name, email_unsubscribed").eq("id", user_id).single().execute()
        if not profile.data or not profile.data.get("email"):
            return
        if profile.data.get("email_unsubscribed"):
            return

        email = profile.data["email"]
        name = profile.data.get("full_name") or email.split("@")[0]
        plan_name = quota_info.plan_name

        from email_service import send_email_async

        if pct >= 1.0:
            from templates.emails.quota import render_quota_exhausted_email
            html = render_quota_exhausted_email(
                user_name=name, plan_name=plan_name,
                quota_limit=max_quota, reset_date=reset_date,
            )
            send_email_async(
                to=email,
                subject=f"Limite de análises atingido — {plan_name}",
                html=html,
                tags=[{"name": "category", "value": "quota_exhausted"}],
            )
        elif pct >= 0.8 and (quota_used - 1) / max_quota < 0.8:
            from templates.emails.quota import render_quota_warning_email
            html = render_quota_warning_email(
                user_name=name, plan_name=plan_name,
                quota_used=quota_used, quota_limit=max_quota,
                reset_date=reset_date,
            )
            send_email_async(
                to=email,
                subject=f"Aviso de cota: {quota_used}/{max_quota} análises usadas",
                html=html,
                tags=[{"name": "category", "value": "quota_warning"}],
            )
    except Exception as e:
        from log_sanitizer import mask_user_id
        logger.error(f"Failed to send quota email for user {mask_user_id(user_id)}: {e}")
        import sentry_sdk
        sentry_sdk.capture_exception(e)

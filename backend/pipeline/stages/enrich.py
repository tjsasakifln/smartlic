"""Stage 5: EnrichResults — relevance scoring, viability, confidence re-ranking, sorting.

Extracted from SearchPipeline.stage_enrich + _enrich_with_sanctions (DEBT-015 SYS-002).
"""

import logging

from relevance import score_relevance, count_phrase_matches
from utils.ordenacao import ordenar_licitacoes
from search_context import SearchContext
from viability import assess_batch as viability_assess_batch
from pipeline.budget import _run_with_budget  # STORY-4.4 TD-SYS-003

logger = logging.getLogger(__name__)

# Budget label for affinity DB lookup (STORY-4.4 TD-SYS-003).
_AFFINITY_BUDGET_S = 5.0  # Lightweight DB call — generous budget, must not block pipeline.


async def stage_enrich(pipeline, ctx: SearchContext) -> None:
    """Compute relevance scores, viability assessment, confidence-based re-ranking, and sorting."""

    # D-04 AC7: Viability assessment (Stage 4.5 — post-filter, pre-ranking)
    # DEBT-128: Viability is always-on (VIABILITY_ASSESSMENT_ENABLED flag removed)
    if ctx.licitacoes_filtradas and not ctx.is_simplified:
        # Get sector-specific value range
        vr = None
        if ctx.sector and hasattr(ctx.sector, "viability_value_range"):
            vr = ctx.sector.viability_value_range
        ufs_busca = set(ctx.request.ufs) if ctx.request.ufs else set()
        # GAP-011: Pass per-sector viability weight overrides if defined
        sector_weights = getattr(ctx.sector, "viability_weights", None) if ctx.sector else None
        viability_assess_batch(
            ctx.licitacoes_filtradas, ufs_busca, vr,
            user_profile=ctx.user_profile,
            custom_terms=ctx.custom_terms or None,
            viability_weights=sector_weights,
        )
        # CRIT-FLT-003 AC4: Log zero-value proportion
        total = len(ctx.licitacoes_filtradas)
        zero_count = sum(
            1 for bid in ctx.licitacoes_filtradas
            if bid.get("_value_source") == "missing"
        )
        zero_pct = round(zero_count / total * 100, 1) if total else 0.0
        logger.info(
            "CRIT-FLT-003: zero_value_stats",
            extra={"zero_value_count": zero_count, "total_bids": total, "zero_value_pct": zero_pct},
        )
        logger.debug(
            f"D-04: Viability assessed for {total} bids. "
            f"Alta: {sum(1 for bid in ctx.licitacoes_filtradas if bid.get('_viability_level') == 'alta')}, "
            f"Media: {sum(1 for bid in ctx.licitacoes_filtradas if bid.get('_viability_level') == 'media')}, "
            f"Baixa: {sum(1 for bid in ctx.licitacoes_filtradas if bid.get('_viability_level') == 'baixa')}, "
            f"Zero-value: {zero_count}/{total} ({zero_pct}%)"
        )

    # Relevance scoring (STORY-178)
    if ctx.custom_terms and ctx.licitacoes_filtradas:
        for lic in ctx.licitacoes_filtradas:
            matched_terms = lic.get("_matched_terms", [])
            phrase_count = count_phrase_matches(matched_terms)
            lic["_relevance_score"] = score_relevance(
                len(matched_terms), len(ctx.custom_terms), phrase_count
            )

    # FEEDBACK-003: Fetch user-sector affinity before scoring.
    # Formula: affinity_factor = min(1.0, 0.5 + affinity).
    #   affinity=0.0 → factor=0.5 (50% reduction, never zero).
    #   affinity=0.5 → factor=1.0 (cold start / neutral).
    #   affinity=1.0 → factor=1.0 (capped — no excessive boost).
    affinity_factor = 1.0  # Neutral default
    if ctx.user and ctx.sector and ctx.licitacoes_filtradas:
        user_id = ctx.user.get("id")
        sector_id = getattr(ctx.sector, "id", None)
        if user_id and sector_id:
            try:
                from feedback_affinity import get_affinity
                from supabase_client import get_supabase

                async def _fetch_affinity():
                    supabase = get_supabase()
                    return await get_affinity(supabase, user_id, sector_id)

                affinity = await _run_with_budget(
                    _fetch_affinity(),
                    budget=_AFFINITY_BUDGET_S,
                    phase="enrich",
                    source="affinity",
                )
                affinity_factor = min(1.0, 0.5 + affinity)
                logger.debug(
                    f"FEEDBACK-003: affinity={affinity:.2f} factor={affinity_factor:.2f} "
                    f"user={user_id[:8]}... sector={sector_id}"
                )
            except Exception as exc:
                logger.warning(f"FEEDBACK-003: affinity lookup failed — using neutral factor: {exc}")

    # D-02 AC5 + D-04 AC9: Re-ranking by combined score (viability always-on)
    if ctx.licitacoes_filtradas:
        viability_active = any(
            bid.get("_viability_score") is not None for bid in ctx.licitacoes_filtradas
        )

        def _confidence_sort_key(lic: dict) -> tuple:
            conf = lic.get("_confidence_score", 50)
            valor = float(lic.get("valorTotalEstimado") or lic.get("valorEstimado") or 0)

            # ISSUE-017 fix: Relevance boost for keyword-matched results.
            # Results matched by actual keywords should rank above LLM-only matches,
            # especially for custom_terms searches where relevance > viability.
            relevance_boost = 0
            if lic.get("_relevance_source") == "keyword":
                relevance_boost += 20
            density = lic.get("_term_density", 0)
            if density and density > 0.03:
                relevance_boost += min(15, int(density * 200))

            if viability_active:
                # D-04 AC9: combined_score = confidence * 0.6 + viability * 0.4
                viab = lic.get("_viability_score", 50)
                combined = conf * 0.6 + viab * 0.4 + relevance_boost
                # FEEDBACK-003: Apply user-sector affinity factor
                combined *= affinity_factor
                lic["_combined_score"] = round(combined)
                lic["_affinity_factor"] = round(affinity_factor, 3)
                return (-combined, -valor)

            # FEEDBACK-003: Fallback for simplified searches without viability scores.
            # Apply affinity consistently so both paths personalize results.
            # Band: 0=high(>=80), 1=medium(50-79), 2=low(<50)
            boosted_conf = (conf + relevance_boost) * affinity_factor
            lic["_affinity_factor"] = round(affinity_factor, 3)
            if boosted_conf >= 80:
                band = 0
            elif boosted_conf >= 50:
                band = 1
            else:
                band = 2
            return (band, -boosted_conf, -valor)

        ctx.licitacoes_filtradas.sort(key=_confidence_sort_key)
        logger.debug(
            f"D-02 AC5: Re-ranked {len(ctx.licitacoes_filtradas)} results by confidence. "
            f"High(>=80): {sum(1 for bid in ctx.licitacoes_filtradas if bid.get('_confidence_score', 50) >= 80)}, "
            f"Medium(50-79): {sum(1 for bid in ctx.licitacoes_filtradas if 50 <= bid.get('_confidence_score', 50) < 80)}, "
            f"Low(<50): {sum(1 for bid in ctx.licitacoes_filtradas if bid.get('_confidence_score', 50) < 50)}"
        )

    # VIAB-UX-005a: A/B test — override default sort when feature flag is active
    try:
        from config import get_feature_flag as _get_ff
        from utils.viability_split import get_viability_sort_group as _get_group

        if _get_ff("VIABILITY_DEFAULT_SORT"):
            user_id = ctx.user.get("id") if ctx.user else None
            if user_id:
                sort_group = _get_group(user_id)
                if sort_group == "B":
                    ctx.request.ordenacao = "confianca"
                    logger.info(
                        "VIAB-UX-005a: Group B override — sorting by confianca "
                        f"(user={user_id[:8]}...)"
                    )
                else:
                    logger.debug(
                        "VIAB-UX-005a: Group A — keeping default sort "
                        f"(user={user_id[:8]}...)"
                    )
    except Exception as exc:
        logger.warning(
            f"VIAB-UX-005a: A/B sort override failed — falling through: {exc}"
        )

    # User-requested sorting (applied AFTER confidence re-ranking for non-default)
    if ctx.licitacoes_filtradas and ctx.request.ordenacao != "data_desc":
        logger.debug(f"Applying user sorting: ordenacao='{ctx.request.ordenacao}'")
        ctx.licitacoes_filtradas = ordenar_licitacoes(
            ctx.licitacoes_filtradas,
            ordenacao=ctx.request.ordenacao,
            termos_busca=ctx.custom_terms if ctx.custom_terms else list(ctx.active_keywords)[:10],
        )

    if ctx.licitacoes_filtradas:
        import time as _sync_time
        filter_elapsed = _sync_time.time() - ctx.start_time
        logger.debug(
            f"Filtering and sorting complete in {filter_elapsed:.2f}s: "
            f"{len(ctx.licitacoes_filtradas)} results ordered by '{ctx.request.ordenacao}'"
        )

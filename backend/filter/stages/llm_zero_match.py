"""LLM Zero Match Classification (#1781)."""
import logging
from typing import Callable, Dict, List, Optional, Tuple

from filter.keywords import normalize_text, _strip_org_context

logger = logging.getLogger(__name__)


def run_llm_zero_match(
    resultado_valor: List[dict],
    resultado_keyword: List[dict],
    setor: Optional[str],
    custom_terms: Optional[List[str]],
    on_progress: Optional[Callable[[int, int, str], None]],
    stats: Dict[str, int],
) -> Tuple[List[dict], Dict[str, int]]:
    """Run LLM zero-match classification on bids rejected by keyword filter."""
    resultado_llm_zero: List[dict] = []
    stats["llm_zero_match_calls"] = 0
    stats["llm_zero_match_aprovadas"] = 0
    stats["llm_zero_match_rejeitadas"] = 0
    stats["llm_zero_match_skipped_short"] = 0
    stats["pending_review_count"] = 0

    _use_term_prompt_zm = False
    if custom_terms:
        from config import get_feature_flag as _gff_ac2
        _use_term_prompt_zm = _gff_ac2("TERM_SEARCH_LLM_AWARE")

    if setor or custom_terms:
        keyword_approved_ids = {id(lic) for lic in resultado_keyword}
        zero_match_pool: List[dict] = []
        for lic in resultado_valor:
            if id(lic) not in keyword_approved_ids:
                objeto = lic.get("objetoCompra", "")
                if len(objeto) < 20:
                    stats["llm_zero_match_skipped_short"] += 1
                    continue
                zero_match_pool.append(lic)

        if zero_match_pool and setor:
            from sectors import get_sector as _get_sector_neg
            _sector_negative_kws: list = []
            try:
                _neg_sec = _get_sector_neg(setor)
                _sector_negative_kws = [kw.lower() for kw in getattr(_neg_sec, "negative_keywords", [])]
            except Exception:
                pass
            if _sector_negative_kws:
                _neg_filtered = []
                _neg_rejected = 0
                for lic in zero_match_pool:
                    _obj_lower = (lic.get("objetoCompra") or "").lower()
                    if any(neg_kw in _obj_lower for neg_kw in _sector_negative_kws):
                        _neg_rejected += 1
                    else:
                        _neg_filtered.append(lic)
                if _neg_rejected > 0:
                    stats["llm_zero_match_neg_prefilter"] = _neg_rejected
                zero_match_pool = _neg_filtered

        if zero_match_pool:
            from llm_arbiter import classify_contract_primary_match as _classify_zm
            from sectors import get_sector as _get_sector_zm

            if setor:
                try:
                    setor_config_zm = _get_sector_zm(setor)
                    setor_name_zm = setor_config_zm.name
                except (KeyError, Exception):
                    setor_name_zm = setor
            elif custom_terms:
                setor_name_zm = ", ".join(custom_terms[:3])

            def _classify_one(lic_item: dict) -> Tuple[dict, dict]:
                obj = lic_item.get("objetoCompra", "")
                obj = _strip_org_context(obj)
                val = lic_item.get("valorTotalEstimado") or lic_item.get("valorEstimado") or 0
                if isinstance(val, str):
                    try:
                        val = float(val.replace(".", "").replace(",", "."))
                    except ValueError:
                        val = 0.0
                else:
                    val = float(val) if val else 0.0
                if _use_term_prompt_zm and custom_terms:
                    result = _classify_zm(
                        objeto=obj, valor=val, setor_name=None,
                        termos_busca=custom_terms, prompt_level="zero_match", setor_id=None,
                    )
                else:
                    result = _classify_zm(
                        objeto=obj, valor=val, setor_name=setor_name_zm,
                        prompt_level="zero_match", setor_id=setor,
                    )
                return lic_item, result

            import asyncio as _asyncio_zm
            from llm_arbiter.async_runtime import gather_classifications as _gather_zm, unwrap_result as _unwrap_zm

            _llm_completed = 0

            def _on_zm_progress(done: int, total: int, phase: str) -> None:
                nonlocal _llm_completed
                _llm_completed = done
                stats["llm_zero_match_calls"] += 1
                if on_progress:
                    on_progress(done, total, phase)

            _paired_results = _asyncio_zm.run(
                _gather_zm(
                    _classify_one, list(zero_match_pool),
                    call_type="zero_match", on_progress=_on_zm_progress,
                )
            )

            class _ResolvedFuture:
                def __init__(self, value): self._v = value
                def result(self): return _unwrap_zm(self._v)

            futures = {_ResolvedFuture(r): None for r in _paired_results}

            for future in futures:
                try:
                    lic_item, llm_result = future.result()
                    is_relevant = llm_result.get("is_primary", False) if isinstance(llm_result, dict) else llm_result
                    if is_relevant and custom_terms:
                        obj_norm = normalize_text(lic_item.get("objetoCompra", ""))
                        has_term_evidence = any(
                            normalize_text(term) in obj_norm for term in custom_terms
                        )
                        if not has_term_evidence:
                            is_relevant = False
                    if is_relevant:
                        stats["llm_zero_match_aprovadas"] += 1
                        if custom_terms:
                            from metrics import TERM_SEARCH_LLM_ACCEPTS
                            TERM_SEARCH_LLM_ACCEPTS.labels(zone="zero_match").inc()
                        lic_item["_relevance_source"] = "llm_zero_match"
                        lic_item["_term_density"] = 0.0
                        lic_item["_matched_terms"] = []
                        if isinstance(llm_result, dict):
                            raw_conf = llm_result.get("confidence", 60)
                            lic_item["_confidence_score"] = min(raw_conf, 70)
                            lic_item["_llm_evidence"] = llm_result.get("evidence", [])
                        else:
                            lic_item["_confidence_score"] = 60
                            lic_item["_llm_evidence"] = []
                        resultado_llm_zero.append(lic_item)
                    else:
                        if isinstance(llm_result, dict) and llm_result.get("pending_review"):
                            stats["pending_review_count"] += 1
                            lic_item["_pending_review"] = True
                            lic_item["_pending_review_reason"] = llm_result.get("rejection_reason", "LLM unavailable")
                        stats["llm_zero_match_rejeitadas"] += 1
                        if custom_terms:
                            from metrics import TERM_SEARCH_LLM_REJECTS
                            TERM_SEARCH_LLM_REJECTS.labels(zone="zero_match").inc()
                        if isinstance(llm_result, dict):
                            lic_item["_llm_rejection_reason"] = llm_result.get("rejection_reason", "")
                except Exception as e:
                    stats["llm_zero_match_rejeitadas"] += 1
                    logger.error(f"LLM zero_match: FAILED (REJECT fallback): {e}")

            if resultado_llm_zero and setor:
                _cb_threshold = 0.30
                try:
                    _sec_cfg_cb = _get_sector_zm(setor)
                    if hasattr(_sec_cfg_cb, "zero_match_acceptance_cap") and _sec_cfg_cb.zero_match_acceptance_cap is not None:
                        _cb_threshold = _sec_cfg_cb.zero_match_acceptance_cap
                except Exception:
                    pass
                _total_classified = stats["llm_zero_match_aprovadas"] + stats["llm_zero_match_rejeitadas"]
                if _total_classified > 0 and stats["llm_zero_match_aprovadas"] / _total_classified > _cb_threshold:
                    for _lic in resultado_llm_zero:
                        _lic["_relevance_source"] = "pending_review"
                        _lic["_pending_review"] = True
                        _lic["_pending_review_reason"] = "zero_match_high_acceptance_ratio"
                    resultado_llm_zero = []

    return resultado_llm_zero, stats

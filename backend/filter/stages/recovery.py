"""FLUXO 2 — Anti-False Negative Recovery Pipeline (#1781)."""
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


def run_fluxo_2_recovery(
    aprovadas: List[dict],
    resultado_valor: List[dict],
    setor: Optional[str],
    custom_terms: Optional[List[str]],
    stats: Dict[str, int],
) -> List[dict]:
    """Run FLUXO 2 recovery pipeline on rejected bids."""
    stats["recuperadas_exclusion_recovery"] = 0
    stats["aprovadas_synonym_match"] = 0
    stats["synonyms_auto_approved"] = 0
    stats["recuperadas_llm_fn"] = 0
    stats["recuperadas_zero_results"] = 0
    stats["llm_arbiter_calls_fn_flow"] = 0
    stats["zero_results_relaxation_triggered"] = False

    _skip_fluxo_2 = stats.get("llm_zero_match_calls", 0) > 0
    if _skip_fluxo_2:
        logger.info(
            "GTM-FIX-028 AC10: FLUXO 2 DISABLED - LLM zero-match already classified "
            f"{stats['llm_zero_match_calls']} bids"
        )

    _use_term_prompt_recovery = False
    _use_term_synonyms = False
    if custom_terms:
        from config import get_feature_flag as _gff_ac4
        _use_term_prompt_recovery = _gff_ac4("TERM_SEARCH_LLM_AWARE")
        _use_term_synonyms = _gff_ac4("TERM_SEARCH_SYNONYMS")

    _run_fluxo_2 = (setor or (_use_term_synonyms and custom_terms)) and not _skip_fluxo_2
    if _run_fluxo_2:
        from synonyms import find_synonym_matches, should_auto_approve_by_synonyms
        if _use_term_synonyms and custom_terms:
            from synonyms import find_term_synonym_matches
        from sectors import get_sector as _get_sector

        try:
            setor_config = _get_sector(setor) if setor else None
            setor_keywords = setor_config.keywords if setor_config else set()
            setor_name = setor_config.name if setor_config else None

            aprovadas_ids = {id(lic) for lic in aprovadas}
            rejeitadas_keyword_pool: List[dict] = []
            for lic in resultado_valor:
                if id(lic) not in aprovadas_ids:
                    rejeitadas_keyword_pool.append(lic)

            recuperadas: List[dict] = []
            llm_candidates_fn: List[dict] = []

            for lic in rejeitadas_keyword_pool:
                objeto = lic.get("objetoCompra", "")
                if not objeto:
                    continue
                if _use_term_synonyms and custom_terms:
                    synonym_matches = find_term_synonym_matches(
                        custom_terms=custom_terms, objeto=objeto,
                    )
                elif setor:
                    synonym_matches = find_synonym_matches(
                        objeto=objeto, setor_keywords=setor_keywords, setor_id=setor,
                    )
                else:
                    synonym_matches = []
                if not synonym_matches:
                    continue
                if _use_term_synonyms and custom_terms:
                    should_approve_flag = len(synonym_matches) >= 2
                    matches = synonym_matches
                else:
                    should_approve_flag, matches = should_auto_approve_by_synonyms(
                        objeto=objeto, setor_keywords=setor_keywords, setor_id=setor, min_synonyms=2,
                    )
                if should_approve_flag:
                    stats["aprovadas_synonym_match"] += 1
                    stats["synonyms_auto_approved"] += 1
                    lic["_recovered_by"] = "synonym_auto_approve"
                    lic["_synonym_matches"] = [f"{canon}={syn}" for canon, syn in matches]
                    recuperadas.append(lic)
                    if custom_terms:
                        from metrics import TERM_SEARCH_SYNONYM_RECOVERIES
                        TERM_SEARCH_SYNONYM_RECOVERIES.inc()
                else:
                    lic["_near_miss_synonyms"] = synonym_matches
                    llm_candidates_fn.append(lic)

            if llm_candidates_fn:
                from filter.keywords import _strip_org_context as _soc
                from llm_arbiter import classify_contract_recovery
                for lic in llm_candidates_fn:
                    objeto = _soc(lic.get("objetoCompra", ""))
                    valor = lic.get("valorTotalEstimado") or lic.get("valorEstimado") or 0
                    if isinstance(valor, str):
                        try:
                            valor = float(valor.replace(".", "").replace(",", "."))
                        except ValueError:
                            valor = 0.0
                    else:
                        valor = float(valor) if valor else 0.0
                    stats["llm_arbiter_calls_fn_flow"] += 1
                    if _use_term_prompt_recovery and custom_terms:
                        should_recover = classify_contract_recovery(
                            objeto=objeto, valor=valor,
                            rejection_reason="keyword_no_match + synonym_near_miss",
                            termos_busca=custom_terms,
                        )
                    else:
                        should_recover = classify_contract_recovery(
                            objeto=objeto, valor=valor,
                            rejection_reason="keyword_no_match + synonym_near_miss",
                            setor_name=setor_name,
                        )
                    if should_recover:
                        stats["recuperadas_llm_fn"] += 1
                        lic["_recovered_by"] = "llm_recovery"
                        recuperadas.append(lic)

            if recuperadas:
                aprovadas.extend(recuperadas)

            if len(aprovadas) == 0 and len(rejeitadas_keyword_pool) > 0:
                stats["zero_results_relaxation_triggered"] = True
                for lic in rejeitadas_keyword_pool:
                    if id(lic) in {id(r) for r in recuperadas}:
                        continue
                    objeto = lic.get("objetoCompra", "")
                    if not objeto:
                        continue
                    if _use_term_synonyms and custom_terms:
                        synonym_matches = find_term_synonym_matches(
                            custom_terms=custom_terms, objeto=objeto,
                        )
                    elif setor:
                        synonym_matches = find_synonym_matches(
                            objeto=objeto, setor_keywords=setor_keywords, setor_id=setor,
                        )
                    else:
                        synonym_matches = []
                    if synonym_matches:
                        stats["recuperadas_zero_results"] += 1
                        lic["_recovered_by"] = "zero_results_relaxation"
                        aprovadas.append(lic)

        except KeyError:
            logger.warning(f"Setor '{setor}' nao encontrado - pulando FLUXO 2")
        except Exception as e:
            logger.error(f"FLUXO 2 recovery failed: {e}", exc_info=True)

    return aprovadas

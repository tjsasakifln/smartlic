"""Batch zero-match classification and recovery functions.

TD-009: Extracted from llm_arbiter.py as part of DEBT-07 module split.
Contains _classify_zero_match_batch(), _parse_batch_response(), and
classify_contract_recovery().
"""

import hashlib
import logging
import re
import time as _time_module
from typing import Optional

from llm_arbiter.classification import (
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TEMPERATURE,
    _arbiter_cache,
    _arbiter_cache_get_redis,
    _arbiter_cache_set,
    _arbiter_cache_set_redis,
    _log_token_usage,
)
from llm_arbiter.prompt_builder import (
    _build_zero_match_batch_prompt,
    _build_zero_match_batch_prompt_terms,
)
from metrics import LLM_CALLS, LLM_DURATION

logger = logging.getLogger(__name__)


def _parse_batch_response(raw_content: str, expected_count: int) -> Optional[list[bool]]:
    """Parse a batch YES/NO response into a list of booleans (AC1, AC5).

    Returns list of booleans (True=YES, False=NO), or None if count mismatch (AC5).
    """
    lines = raw_content.strip().split("\n")
    results = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^\d+[\.\):\s]*\s*(YES|NO|SIM|NAO|NÃO)\s*$', line, re.IGNORECASE)
        if match:
            decision = match.group(1).upper()
            results.append(decision in ("YES", "SIM"))

    if len(results) != expected_count:
        logger.warning(
            f"UX-402 AC5: Batch response count mismatch: "
            f"expected={expected_count}, got={len(results)}. "
            f"Rejecting all (zero noise philosophy). Raw: {raw_content[:300]!r}"
        )
        return None

    return results


def _classify_zero_match_batch(
    items: list[dict],
    setor_name: Optional[str] = None,
    setor_id: Optional[str] = None,
    termos_busca: Optional[list[str]] = None,
    search_id: str = "",
) -> list[dict]:
    """Classify multiple zero-match items in a single LLM call (AC1).

    Sends up to 20 items per batch. Returns list of classification results
    in the same order as input items.
    """
    from config import LLM_ZERO_MATCH_BATCH_TIMEOUT

    if not items:
        return []

    if termos_busca:
        user_prompt = _build_zero_match_batch_prompt_terms(termos_busca, items)
    else:
        user_prompt = _build_zero_match_batch_prompt(setor_id, setor_name or "", items)

    system_prompt = (
        "Você é um classificador conservador de licitações públicas. "
        "Em caso de dúvida, responda NO. "
        "Responda APENAS com uma lista numerada de YES ou NO."
    )

    try:
        _llm_start = _time_module.time()
        # Lazy import via facade so patch("llm_arbiter._get_client") works in tests (AC2)
        import llm_arbiter as _lm
        response = _lm._get_client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max(len(items) * 15, 100),
            temperature=LLM_TEMPERATURE,
            timeout=LLM_ZERO_MATCH_BATCH_TIMEOUT,
        )
        _llm_elapsed = _time_module.time() - _llm_start

        raw_content = response.choices[0].message.content.strip()

        usage = getattr(response, "usage", None)
        if usage and search_id:
            _log_token_usage(
                search_id,
                input_tokens=getattr(usage, "prompt_tokens", 0),
                output_tokens=getattr(usage, "completion_tokens", 0),
            )

        decisions = _parse_batch_response(raw_content, len(items))

        if decisions is None:
            LLM_CALLS.labels(model=LLM_MODEL, decision="BATCH_MISMATCH", zone="zero_match_batch").inc()
            return [
                {
                    "is_primary": False,
                    "confidence": 0,
                    "evidence": [],
                    "rejection_reason": "Batch response count mismatch",
                    "needs_more_data": False,
                }
                for _ in items
            ]

        results = []
        yes_count = 0
        no_count = 0
        for is_yes in decisions:
            if is_yes:
                yes_count += 1
                results.append({
                    "is_primary": True,
                    "confidence": 60,
                    "evidence": [],
                    "rejection_reason": None,
                    "needs_more_data": False,
                })
            else:
                no_count += 1
                results.append({
                    "is_primary": False,
                    "confidence": 0,
                    "evidence": [],
                    "rejection_reason": "LLM batch: not primarily about sector",
                    "needs_more_data": False,
                })

        LLM_DURATION.labels(model=LLM_MODEL, decision="BATCH").observe(_llm_elapsed)
        LLM_CALLS.labels(model=LLM_MODEL, decision="SIM", zone="zero_match_batch").inc(yes_count)
        LLM_CALLS.labels(model=LLM_MODEL, decision="NAO", zone="zero_match_batch").inc(no_count)

        logger.info(
            f"UX-402: Batch zero-match classified {len(items)} items in {_llm_elapsed:.2f}s: "
            f"{yes_count} YES, {no_count} NO"
        )

        return results

    except Exception as e:
        LLM_CALLS.labels(model=LLM_MODEL, decision="ERROR", zone="zero_match_batch").inc()
        logger.error(f"UX-402: Batch zero-match FAILED: {e}")
        raise  # Let caller handle fallback


def classify_contract_recovery(
    objeto: str,
    valor: float,
    rejection_reason: str,
    setor_name: Optional[str] = None,
    termos_busca: Optional[list[str]] = None,
    near_miss_info: Optional[str] = None,
) -> bool:
    """Use LLM to determine if a REJECTED contract should be RECOVERED (STORY-179 AC13).

    Recovery always uses binary mode (no structured output needed).
    """
    # DEBT-128: LLM_ARBITER_ENABLED removed — always-on.
    if not setor_name and not termos_busca:
        logger.error(
            "classify_contract_recovery called without setor_name or termos_busca"
        )
        return False

    objeto_truncated = objeto[:500]

    if setor_name:
        mode = "setor_recovery"
        context = setor_name
        additional_info = f"\nMotivo da rejeição: {rejection_reason}"
        if near_miss_info:
            additional_info += f"\nSinônimos encontrados: {near_miss_info}"

        user_prompt = f"""Este contrato foi REJEITADO automaticamente por: {rejection_reason}

Setor: {setor_name}
Valor: R$ {valor:,.2f}
Objeto: {objeto_truncated}
{additional_info if near_miss_info else ""}

Apesar da rejeição automática, este contrato é RELEVANTE para {setor_name}?
Responda APENAS: SIM ou NAO"""
    else:
        mode = "termos_recovery"
        context = ", ".join(termos_busca) if termos_busca else ""
        user_prompt = f"""Este contrato foi REJEITADO automaticamente por: {rejection_reason}

Termos buscados: {context}
Valor: R$ {valor:,.2f}
Objeto: {objeto_truncated}

Apesar da rejeição, os termos buscados descrevem o OBJETO PRINCIPAL deste contrato?
Responda APENAS: SIM ou NAO"""

    cache_key = hashlib.md5(
        f"{mode}:{context}:{valor}:{objeto_truncated}:{rejection_reason}".encode()
    ).hexdigest()

    if cache_key in _arbiter_cache:
        _arbiter_cache.move_to_end(cache_key)
        cached = _arbiter_cache[cache_key]
        if isinstance(cached, dict):
            return cached.get("is_primary", False)
        return cached

    redis_cached = _arbiter_cache_get_redis(cache_key)
    if redis_cached is not None:
        if isinstance(redis_cached, dict):
            return redis_cached.get("is_primary", False)
        return redis_cached

    try:
        system_prompt = (
            "Você é um classificador de licitações que avalia se contratos rejeitados "
            "automaticamente são relevantes. Responda APENAS 'SIM' ou 'NAO'."
        )

        _llm_start = _time_module.time()
        # Lazy import via facade so patch("llm_arbiter._get_client") works in tests (AC2)
        import llm_arbiter as _lm
        response = _lm._get_client().chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
        )
        _llm_elapsed = _time_module.time() - _llm_start

        llm_response = response.choices[0].message.content.strip().upper()
        should_recover = llm_response == "SIM"

        _decision = "SIM" if should_recover else "NAO"
        LLM_DURATION.labels(model=LLM_MODEL, decision=_decision).observe(_llm_elapsed)
        LLM_CALLS.labels(model=LLM_MODEL, decision=_decision, zone="recovery").inc()

        _arbiter_cache_set(cache_key, should_recover)
        _arbiter_cache_set_redis(cache_key, should_recover)

        logger.debug(
            f"LLM recovery decision: {llm_response} | "
            f"mode={mode} reason={rejection_reason} valor={valor:,.2f}"
        )

        return should_recover

    except Exception as e:
        LLM_CALLS.labels(model=LLM_MODEL, decision="ERROR", zone="recovery").inc()
        logger.error(
            f"LLM recovery FAILED (defaulting to NO RECOVERY): {e} | "
            f"mode={mode} reason={rejection_reason} valor={valor:,.2f}"
        )
        return False

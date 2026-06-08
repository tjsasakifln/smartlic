# AI Classification Pipeline

> **How SmartLic uses LLMs as bounded arbiters inside a cost-controlled classification pipeline
> with hallucination checks — not as oracular generators.**

---

## Overview

SmartLic classifies ~10,000 daily government tenders into 20 industry sectors. The challenge:
government text is ambiguous, keyword-only matching produces catastrophic false positives, and
naive GPT-4 classification would cost ~$50/day and introduce hallucination risk.

**Solution:** a 3-tier hybrid pipeline where deterministic filters handle ~80% of volume,
keyword density scoring handles ~15%, and GPT-4.1-nano arbitrates only the ambiguous ~5% —
with structured output, evidence requirements, and automated fallback on malformed responses.

**Cost impact:** LLM invoked on ~2-4% of total tender volume. Monthly classification cost:
~$5–15. This is viable at a SaaS price point of R$297–997/month.

---

## Pipeline Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    RAW TENDER TEXT                       │
└────────────────────────┬────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────┐
│ TIER 1: DETERMINISTIC FILTERS                           │
│                                                         │
│  □ UF match (exact, 27 Brazilian states)                │
│  □ Value range (min/max configured per sector)          │
│  □ Date range (publication window)                       │
│  □ Modality filter (6 procurement types)                │
│  □ Status filter (open/closed/canceled)                 │
│                                                         │
│  Cost: $0 (pure Python string/int comparison)           │
│  Rejection: immediate, no further processing            │
└────────────────────────┬────────────────────────────────┘
                         │ ~80% pass
                         ▼
┌─────────────────────────────────────────────────────────┐
│ TIER 2: KEYWORD DENSITY SCORING                         │
│                                                         │
│  Input: tender description + objeto (subject)            │
│  Process:                                                │
│    1. Tokenize (Portuguese, remove stopwords)           │
│    2. Match against sector keywords (sectors_data.yaml) │
│    3. Apply context_required_keywords (must co-occur)   │
│    4. Apply exclusion keywords (if present → reject)    │
│    5. Compute density = matched / total tokens          │
│                                                         │
│  Output:                                                 │
│    >5% density → APPROVED (keyword tier, no LLM)        │
│    2-5% density → AMBIGUOUS (LLM standard, verify)      │
│    1-2% density → AMBIGUOUS (LLM conservative, strict)  │
│    0% density   → LLM_ZERO_MATCH (LLM decides YES/NO)   │
│                                                         │
│  Cost: $0 (pure Python, no API call)                    │
│  Accuracy: precision 90%+, recall 60% (high precision,  │
│            known false negative rate from ambiguous text)│
└────────────────────────┬────────────────────────────────┘
                         │ ~5% reach LLM
                         ▼
┌─────────────────────────────────────────────────────────┐
│ TIER 3: LLM ARBITER (GPT-4.1-nano)                      │
│                                                         │
│  Invocation conditions:                                  │
│    • Density 0-5% (ambiguous or zero keyword match)     │
│    • Feature flag LLM_ARBITER_ENABLED=true              │
│    • Sector has LLM prompt defined                      │
│    • Not rate-limited (concurrent call cap)             │
│                                                         │
│  Cost: ~$0.0001–0.0003 per classification               │
│  Latency: +50ms avg, p95 < 150ms                        │
└─────────────────────────────────────────────────────────┘
```

---

## LLM Arbiter Design

### Prompt Structure

Each sector has a structured prompt (built by `llm_arbiter/prompt_builder.py`):

```
System: You are a government procurement classifier for the sector "{sector_name}".
        Sector definition: {description}
        Keywords that indicate relevance: {keywords}
        Context-required keywords (must appear together): {context_required}
        Keywords that indicate IRRELEVANCE: {exclusions}

        RULES:
        1. The tender MUST involve {sector_name} as its PRIMARY object.
        2. If {sector_name} is incidental (<10% of contract value), REJECT.
        3. If {exclusion_keywords} dominate, REJECT.
        4. You MUST quote the specific text that supports your decision.

User: Tender: {title} | {description}
      Value: {value} | Modality: {modality} | Agency: {orgao}

      Classify as APPROVE or REJECT. Provide evidence.
```

### Structured Output

LLM response is validated against this Pydantic schema:

```python
class LlmArbiterVerdict(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    evidence: str  # Must be non-empty, must be a substring of tender text
    confidence: float  # 0.0–1.0
    reasoning: str  # Max 200 chars, explanation of decision
```

If the LLM returns malformed JSON, the parser catches it and falls back to `PENDING_REVIEW`
(when `LLM_FALLBACK_PENDING_ENABLED=true`) or `REJECT` (when disabled). The system never
passes unvalidated LLM output downstream.

### Temperature

`temperature=0` for all classification calls. The task is deterministic (APPROVE/REJECT),
not creative. Higher temperature would introduce variance without benefit.

### Concurrency

`ThreadPoolExecutor(max_workers=10)` for parallel LLM calls during batch classification.
ARQ background jobs for executive summaries (separate, lower-priority path).

---

## Cost Control

### Why GPT-4.1-nano

- Cheapest OpenAI model with sufficient Portuguese comprehension
- Classification task is bounded (YES/NO) — doesn't need GPT-4's reasoning depth
- Latency ~50ms per call, well within budget

### Cost Tracking

```
smartlic_llm_classification_cost_total{sector, tier}
smartlic_llm_summary_cost_total
smartlic_llm_fallback_rejects_total{reason}
```

Tracked per search session, per sector, per billing period. Admin dashboard at
`GET /v1/admin/llm-cost` surfaces cost trends and anomalies.

### Batch Fallback

If the LLM API is unreachable or rate-limited, the system:
1. Logs the failure with Prometheus counter
2. Falls back to keyword-only classification for that batch
3. Flags the search session as "LLM degraded" (shown in UI via `LlmSourceBadge`)

This prevents LLM outages from blocking the entire search pipeline.

---

## Anti-Hallucination Measures

| Measure | What It Prevents | Implementation |
|---------|-----------------|----------------|
| Structured output schema | Free-text hallucination, invented fields | Pydantic `LlmArbiterVerdict` — parse failure → fallback |
| Evidence requirement | Classification without basis | Prompt requires text quote; parser checks non-empty |
| Temperature = 0 | Stochastic variance, inconsistent answers | OpenAI API parameter |
| Decision boundary (APPROVE/REJECT only) | LLM role creep, creative generation | Enum constraint in schema |
| Sector-specific exclusion keywords | Context-blind keyword matching | `sectors_data.yaml` exclusions checked BEFORE LLM call |
| Context-required keyword co-occurrence | False positives from single-word matches | `sectors_data.yaml` context_required_keywords — must co-occur |
| Feedback loop | Drift in classification quality over time | User feedback → bi-gram analysis → exclusion rule suggestions |
| Cost anomaly detection | Runaway LLM calls | Prometheus counter + admin dashboard + cost alert threshold |

---

## Sector Configuration

20 sectors defined in `backend/sectors_data.yaml`. Each sector entry:

```yaml
sectors:
  - id: "limpeza_e_conservacao"
    name: "Limpeza e Conservação"
    description: "Serviços de limpeza predial, conservação, higienização..."
    keywords:
      - "limpeza"
      - "higienização"
      - "faxina"
      - "asseio"
      # ...30+ keywords per sector
    exclusions:
      - "limpeza urbana"      # Urban cleaning ≠ building cleaning
      - "limpeza de terrenos"  # Lot cleaning ≠ building cleaning
      - "coleta de lixo"       # Waste collection ≠ cleaning
    context_required_keywords:
      - ["limpeza", "predial"]  # Must appear together
      - ["higienização", "banheiro"]
    viability_value_range:
      min: 5000
      max: 5000000
```

Exclusion keywords and context requirements are the primary defense against the
"uniformes in a R$47.6M infrastructure contract" false positive problem.
Sectors are versioned — changes to keywords require benchmark re-validation
(15 samples/sector, precision ≥85%, recall ≥70%).

---

## Quality Assurance

### Benchmark

`tests/test_llm_arbiter_benchmark.py` — 20 sectors × 15 labeled samples = 300-label evaluation set.
Run on every prompt change. Measures:

- **Precision:** TP / (TP + FP) — what fraction of APPROVEs are correct?
- **Recall:** TP / (TP + FN) — what fraction of truly relevant tenders did we catch?

Threshold: precision ≥85%, recall ≥70%. The benchmark deliberately accepts lower recall
because false positives erode user trust more than false negatives (users can search
broadly, but they can't unsee bad classifications).

### Feedback System

Users can flag misclassified tenders (thumbs up/down). Each feedback record:
- Links to the specific bid and classification decision
- Runs a bi-gram overlap analysis against sector keywords
- Surfaces exclusion rule candidates to admin dashboard

The goal: automated detection of keyword patterns that cause false positives,
enabling exclusion rule updates without manual review of every misclassification.

---

## Integration Points

| Component | File | Role |
|-----------|------|------|
| Keyword density | `filter/keywords.py`, `filter/density.py` | Tier 2 scoring |
| LLM arbiter | `llm_arbiter/classification.py` | Tier 3 dispatch (standard/conservative) |
| Zero-match LLM | `llm_arbiter/zero_match.py` | Tier 3 for 0% density cases |
| Prompt builder | `llm_arbiter/prompt_builder.py` | Sector-specific prompt assembly |
| Async runtime | `llm_arbiter/async_runtime.py` | ThreadPoolExecutor for parallel calls |
| Batch API | `llm_arbiter/batch_api.py` | Batch classification (ARQ job) |
| Sector config | `sectors_data.yaml` | Keywords, exclusions, context requirements |
| Feedback | `routes/feedback.py`, `feedback_analyzer.py` | User feedback → exclusion candidates |
| LLM summaries | `llm.py` | Executive summaries (separate, non-classification) |

---

## Related Documents

- [LLM Arbiter Architecture](./architecture/llm-arbiter.md) — 4-layer false positive elimination (STORY-179 era, design rationale)
- [System Architecture](./architecture/system-architecture.md) — full module map, ERD
- [CASE STUDY](../CASE_STUDY.md) — engineering narrative

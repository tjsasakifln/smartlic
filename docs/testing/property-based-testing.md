# Property-Based Testing with Hypothesis

## Overview

Property-based testing complements example-based tests by checking **invariant
properties** across a wide range of automatically generated inputs. Instead of
writing "give it X, expect Y", you write "for *any* valid input, property P
should always hold."

This project uses [Hypothesis](https://hypothesis.readthedocs.io/) for
property-based tests targeting the most critical schemas, data-transformation
pipelines, and core utilities.

## Why Property-Based Testing?

| Example-based | Property-based |
|---|---|
| Tests known edge cases | Discovers *unknown* edge cases |
| Brittle — breaks when spec changes | Resilient — invariant rarely changes |
| Low input diversity | High input diversity (strategies) |
| Requires you to predict failure | Finds failure for you (shrinking) |

## Test Modules

All property tests live under `backend/tests/property/`.

| Module | Target | Invariant |
|---|---|---|
| `test_schemas.py` | `BuscaRequest` | Round-trip serialization without loss; date range <= 30d; valor_min <= valor_max |
| `test_search_context.py` | `SearchContext` | `|filtradas| <= |raw|`; deadline_remaining >= 0; valid response_state |
| `test_dedup.py` | `DeduplicationEngine` | `|output| <= |input|`; idempotent on 2nd pass; single-record passthrough |
| `test_search_hash.py` | `compute_search_hash*` | Deterministic; order-independent for lists (UF, modalidades); empty-vs-None equivalence |
| `test_filter_pipeline.py` | `aplicar_todos_filtros` | UF filter monotonic (never increases count); all approved bids have UF in selected set; stats match reality |

## How to Run

```bash
# Default: 10 examples per test (fast local dev)
cd backend && .venv/bin/pytest tests/property/ -v

# CI mode: 100 examples per test
cd backend && .venv/bin/pytest tests/property/ -v --hypothesis-profile=ci

# Full mode: 200 examples per test (weekly/ad-hoc deep check)
cd backend && .venv/bin/pytest tests/property/ -v --hypothesis-profile=ci-full
```

## Hypothesis Profiles

Configured in `backend/tests/property/conftest.py`:

| Profile | Max Examples | Suppressed Health Checks | Use Case |
|---|---|---|---|
| `dev` (default) | 10 | none | Local development |
| `ci` | 100 | `too_slow`, `data_too_large` | CI pipeline |
| `ci-full` | 200 | `too_slow`, `data_too_large` | Deep (weekly/ad-hoc) |

## Writing Property Tests

### Pattern

1. **Define a Hypothesis strategy** for generating valid inputs
2. **State the invariant** in the test name and docstring
3. **Use `@given()`** to feed generated inputs
4. **Use `assume()`** for preconditions (filters out invalid combinations)
5. **Use `@st.settings(deadline=2000)`** to set test-specific timeouts

### Best Practices

- Keep strategies **minimal** — only generate what the function under test needs
- Prefer `st.just()`, `st.sampled_from()`, and `st.lists()` for structured data
- Use `st.builds()` only when the constructor is purely computational (no I/O)
- Avoid mocking in strategies — mock at the test level if needed
- Use `assume()` sparingly — too many assumptions = wasted examples
- Set `deadline=2000` for tests that may involve non-trivial computation
- Test **both** the happy path and the failure path (using `pytest.raises`)

### Example

```python
@given(valid_busca_request())
@st.settings(deadline=2000)
def test_round_trip_serialization(self, request: BuscaRequest):
    """Serialize → deserialize → equal model."""
    as_dict = request.model_dump()
    restored = BuscaRequest(**as_dict)
    assert restored.model_dump() == as_dict
```

## CI Integration

Property tests run as part of the standard backend test suite:

```bash
pytest tests/property/ --hypothesis-profile=ci
```

The CI profile (100 examples) provides a good trade-off between coverage and
runtime. The `too_slow` health check is suppressed in CI because some strategies
generate complex inputs that trigger multi-path validation.

## Adding New Property Tests

1. Create a new file in `backend/tests/property/` named `test_<target>.py`
2. Define strategies at module level or as `@st.composite` functions
3. Write test methods grouped in a `Test*` class
4. Use `@pytest.mark.fuzz` marker to tag the test as property-based
5. Add the test to this table in the documentation

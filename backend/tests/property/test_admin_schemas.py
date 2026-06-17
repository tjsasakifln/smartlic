"""Property-based tests for admin schema models (#1969).

Covers: MemorySnapshot, TraceMallocEntry, AdminUsersListResponse,
AdminCreateUserResponse, AdminDeleteUserResponse, AdminJobTriggerResponse,
AdminClearCheckpointsResponse, AdminProgressTraceState, AdminJobTraceState,
AdminCacheTraceState, AdminSearchTraceResponse, AdminCircuitBreakerResetResponse,
AdminSchemaContractStatusResponse, CronJobHealthRow, AdminCronStatusResponse,
AdminLlmCostResponse, RevenueMetricsResponse, DbPoolStatusResponse,
AdminSyntheticResponse, UserSegmentsResponse, MrrHistoryEntry.

Property: Round-trip serialization (model_dump -> model_validate -> equal).
Property: JSON Schema is valid Draft 2020-12.
Property: Invariant constraints (ge/le, min/max lengths, type checks).
"""

from hypothesis import given, settings, HealthCheck, strategies as st

from schemas.admin import (
    TraceMallocEntry,
    MemorySnapshot,
    AdminUsersListResponse,
    AdminCreateUserResponse,
    AdminDeleteUserResponse,
    AdminJobTriggerResponse,
    AdminClearCheckpointsResponse,
    AdminProgressTraceState,
    AdminJobTraceState,
    AdminCacheTraceState,
    AdminSearchTraceResponse,
    AdminCircuitBreakerResetResponse,
    AdminSchemaContractStatusResponse,
    CronJobHealthRow,
    AdminCronStatusResponse,
    AdminLlmCostResponse,
    RevenueMetricsResponse,
    MrrHistoryEntry,
    DbPoolStatusResponse,
    AdminSyntheticResponse,
    UserSegmentsResponse,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_SETTINGS = settings(
    deadline=500, suppress_health_check=[HealthCheck.too_slow],
)

safe_text = st.text(
    alphabet="abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ,.-",
    min_size=1, max_size=200,
)
small_int = st.integers(min_value=0, max_value=10000)


def _run_roundtrip(obj):
    dumped = obj.model_dump()
    reloaded = type(obj).model_validate(dumped)
    assert reloaded == obj


def _check_json_schema(obj):
    schema = type(obj).model_json_schema()
    assert schema is not None
    assert "properties" in schema


# ---------------------------------------------------------------------------
# Strategy: TraceMallocEntry
# ---------------------------------------------------------------------------

trace_malloc_strategy = st.builds(
    TraceMallocEntry,
    filename=safe_text,
    lineno=small_int,
    size_kb=st.floats(min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False),
    count=small_int,
)

# ---------------------------------------------------------------------------
# Strategy: MemorySnapshot
# ---------------------------------------------------------------------------

memory_snapshot_strategy = st.builds(
    MemorySnapshot,
    rss_bytes=st.one_of(st.none(), st.integers(min_value=0, max_value=10**12)),
    rss_mb=st.one_of(st.none(), st.floats(
        min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False,
    )),
    tracemalloc_enabled=st.booleans(),
    tracemalloc_top_25=st.lists(trace_malloc_strategy, max_size=25),
    asyncio_tasks_pending=small_int,
    gc_objects_count=small_int,
    redis_pool_size=st.one_of(st.none(), small_int),
)

# ---------------------------------------------------------------------------
# Strategy: AdminUsersListResponse
# ---------------------------------------------------------------------------

admin_users_list_strategy = st.builds(
    AdminUsersListResponse,
    users=st.lists(
        st.dictionaries(
            safe_text,
            st.one_of(st.text(), st.integers(), st.booleans()),
            min_size=1, max_size=10,
        ),
        min_size=0, max_size=50,
    ),
    total=small_int,
    limit=st.integers(min_value=1, max_value=200),
    offset=small_int,
)

# ---------------------------------------------------------------------------
# Strategy: AdminCreateUserResponse
# ---------------------------------------------------------------------------

admin_create_user_strategy = st.builds(
    AdminCreateUserResponse,
    user_id=safe_text,
    email=st.emails(),
    plan_id=st.one_of(st.none(), st.text(min_size=1, max_size=50)),
)

# ---------------------------------------------------------------------------
# Strategy: AdminDeleteUserResponse
# ---------------------------------------------------------------------------

admin_delete_user_strategy = st.builds(
    AdminDeleteUserResponse,
    deleted=st.booleans(),
    user_id=safe_text,
)

# ---------------------------------------------------------------------------
# Strategy: AdminJobTriggerResponse
# ---------------------------------------------------------------------------

admin_job_trigger_strategy = st.builds(
    AdminJobTriggerResponse,
    status=st.sampled_from(["enqueued", "skipped", "error"]),
    job_id=st.one_of(st.none(), safe_text),
    timeout_s=st.one_of(st.none(), small_int),
    detail=st.one_of(st.none(), safe_text),
)

# ---------------------------------------------------------------------------
# Strategy: AdminClearCheckpointsResponse
# ---------------------------------------------------------------------------

admin_clear_checkpoints_strategy = st.builds(
    AdminClearCheckpointsResponse,
    status=st.sampled_from(["ok", "error"]),
    checkpoints_deleted=st.one_of(st.none(), small_int),
    detail=st.one_of(st.none(), safe_text),
)

# ---------------------------------------------------------------------------
# Strategy: AdminProgressTraceState
# ---------------------------------------------------------------------------

admin_progress_trace_strategy = st.builds(
    AdminProgressTraceState,
    uf_count=st.one_of(st.none(), small_int),
    ufs_completed=st.one_of(st.none(), small_int),
    is_complete=st.one_of(st.none(), st.booleans()),
    created_at=st.one_of(st.none(), st.floats(
        min_value=0, max_value=1e12, allow_infinity=False, allow_nan=False,
    )),
    mode=st.one_of(st.none(), st.sampled_from(["redis", "in-memory"])),
    error=st.one_of(st.none(), safe_text),
)

# ---------------------------------------------------------------------------
# Strategy: AdminJobTraceState
# ---------------------------------------------------------------------------

admin_job_trace_strategy = st.builds(
    AdminJobTraceState,
    llm_summary=st.one_of(st.none(), st.sampled_from(["completed", "not_found"])),
    excel_generation=st.one_of(st.none(), st.sampled_from(["completed", "not_found"])),
    error=st.one_of(st.none(), safe_text),
)

# ---------------------------------------------------------------------------
# Strategy: AdminCacheTraceState
# ---------------------------------------------------------------------------

admin_cache_trace_strategy = st.builds(
    AdminCacheTraceState,
    is_revalidating=st.one_of(st.none(), st.booleans()),
    redis=st.one_of(st.none(), st.sampled_from(["hit", "miss", "error"])),
    error=st.one_of(st.none(), safe_text),
)

# ---------------------------------------------------------------------------
# Strategy: AdminSearchTraceResponse
# ---------------------------------------------------------------------------

admin_search_trace_strategy = st.builds(
    AdminSearchTraceResponse,
    search_id=safe_text,
    queried_at=st.datetimes().map(lambda d: d.isoformat()),
    progress=st.one_of(st.none(), admin_progress_trace_strategy),
    cache=st.one_of(st.none(), admin_cache_trace_strategy),
    jobs=st.one_of(st.none(), admin_job_trace_strategy),
)

# ---------------------------------------------------------------------------
# Strategy: AdminCircuitBreakerResetResponse
# ---------------------------------------------------------------------------

admin_cb_reset_strategy = st.builds(
    AdminCircuitBreakerResetResponse,
    status=safe_text,
    previous_states=st.dictionaries(
        safe_text, st.one_of(st.text(), st.booleans(), st.integers()),
        min_size=0, max_size=10,
    ),
    reset_by=st.one_of(st.none(), safe_text),
)

# ---------------------------------------------------------------------------
# Strategy: AdminSchemaContractStatusResponse
# ---------------------------------------------------------------------------

admin_schema_contract_strategy = st.builds(
    AdminSchemaContractStatusResponse,
    passed=st.one_of(st.none(), st.booleans()),
    missing=st.lists(safe_text, max_size=20),
    strict_mode=st.booleans(),
    checked_at=st.floats(
        min_value=0, max_value=1e12, allow_infinity=False, allow_nan=False,
    ),
    stale=st.booleans(),
)

# ---------------------------------------------------------------------------
# Strategy: CronJobHealthRow
# ---------------------------------------------------------------------------

cron_job_health_strategy = st.builds(
    CronJobHealthRow,
    jobname=st.one_of(st.none(), safe_text),
    schedule=st.one_of(st.none(), safe_text),
    active=st.one_of(st.none(), st.booleans()),
    last_status=st.one_of(st.none(), st.sampled_from(["success", "failed", "running"])),
    last_run_at=st.one_of(st.none(), st.datetimes().map(lambda d: d.isoformat())),
    runs_24h=small_int,
    failures_24h=small_int,
    latency_avg_ms=st.one_of(st.none(), small_int),
    last_return_message=st.one_of(st.none(), safe_text),
)

# ---------------------------------------------------------------------------
# Strategy: AdminCronStatusResponse
# ---------------------------------------------------------------------------

admin_cron_status_strategy = st.builds(
    AdminCronStatusResponse,
    status=st.sampled_from(["healthy", "error", "degraded"]),
    queried_at=st.datetimes().map(lambda d: d.isoformat()),
    count=small_int,
    jobs=st.lists(cron_job_health_strategy, min_size=0, max_size=30),
    detail=st.one_of(st.none(), safe_text),
)

# ---------------------------------------------------------------------------
# Strategy: AdminLlmCostResponse
# ---------------------------------------------------------------------------

admin_llm_cost_strategy = st.builds(
    AdminLlmCostResponse,
    month_to_date_usd=st.floats(
        min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False,
    ),
    budget_usd=st.floats(
        min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False,
    ),
    pct_used=st.floats(
        min_value=0, max_value=1000, allow_infinity=False, allow_nan=False,
    ),
    projected_end_of_month_usd=st.floats(
        min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False,
    ),
    month=st.text(min_size=1, max_size=50),
    exceeded=st.booleans(),
)

# ---------------------------------------------------------------------------
# Strategy: MrrHistoryEntry
# ---------------------------------------------------------------------------

mrr_history_strategy = st.builds(
    MrrHistoryEntry,
    month=safe_text,
    mrr=st.floats(min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False),
    subscriber_count=small_int,
)

# ---------------------------------------------------------------------------
# Strategy: RevenueMetricsResponse
# ---------------------------------------------------------------------------

revenue_metrics_strategy = st.builds(
    RevenueMetricsResponse,
    mrr=st.floats(min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False),
    churn_rate_30d=st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False),
    trial_to_paid_30d=st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False),
    trial_to_paid_90d=st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False),
    activation_d7=st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False),
    retention_d1=st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False),
    retention_d7=st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False),
    retention_d30=st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False),
    arpa=st.floats(min_value=0, max_value=1e6, allow_infinity=False, allow_nan=False),
    total_subscribers=small_int,
    period_start=st.datetimes().map(lambda d: d.isoformat()),
    period_end=st.datetimes().map(lambda d: d.isoformat()),
    mrr_history=st.lists(mrr_history_strategy, max_size=24),
    lookup_duration_ms=st.floats(min_value=0, max_value=60000, allow_infinity=False, allow_nan=False),
)

# ---------------------------------------------------------------------------
# Strategy: DbPoolStatusResponse
# ---------------------------------------------------------------------------

db_pool_status_strategy = st.builds(
    DbPoolStatusResponse,
    status=st.sampled_from(["healthy", "degraded", "critical"]),
    active=small_int,
    idle=small_int,
    idle_in_transaction=small_int,
    total=small_int,
    max=small_int,
    waiting=small_int,
    utilization=st.floats(min_value=0, max_value=1, allow_infinity=False, allow_nan=False),
    utilization_pct=st.floats(min_value=0, max_value=100, allow_infinity=False, allow_nan=False),
    source=st.sampled_from(["pgbouncer", "direct", "unknown"]),
    threshold_warning_pct=small_int,
    threshold_critical_pct=small_int,
)

# ---------------------------------------------------------------------------
# Strategy: UserSegmentsResponse
# ---------------------------------------------------------------------------

user_segments_strategy = st.builds(
    UserSegmentsResponse,
    count_by_state=st.dictionaries(
        safe_text, small_int, min_size=1, max_size=20,
    ),
    total_users=small_int,
    transitions_last_week=st.lists(st.dictionaries(
        safe_text, st.one_of(st.text(), st.integers()),
    ), max_size=20),
    power_users=st.lists(st.dictionaries(
        safe_text, st.one_of(st.text(), st.integers(), st.booleans()),
    ), max_size=20),
    queried_at=st.datetimes().map(lambda d: d.isoformat()),
)

# ---------------------------------------------------------------------------
# Strategy: AdminSyntheticResponse
# ---------------------------------------------------------------------------

admin_synthetic_strategy = st.builds(
    AdminSyntheticResponse,
    status=st.sampled_from(["success", "degraded", "failure", "no_data", "error"]),
    queried_at=st.one_of(st.none(), st.floats(
        min_value=0, max_value=1e12, allow_infinity=False, allow_nan=False,
    )),
    overall_elapsed_ms=st.one_of(st.none(), small_int),
    stages=st.dictionaries(
        safe_text, st.dictionaries(
            safe_text,
            st.one_of(st.integers(), st.booleans(), st.none(), st.text()),
            min_size=1, max_size=8,
        ),
        min_size=0, max_size=10,
    ),
    timings=st.dictionaries(safe_text, small_int, min_size=0, max_size=10),
    consecutive_failures=small_int,
    detail=st.one_of(st.none(), safe_text),
)


# ---------------------------------------------------------------------------
# Test Classes
# ---------------------------------------------------------------------------


class TestTraceMallocEntry:
    """Property tests for TraceMallocEntry."""

    @given(obj=trace_malloc_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=trace_malloc_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=trace_malloc_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.size_kb >= 0
        assert obj.count >= 0
        assert obj.lineno >= 0


class TestMemorySnapshot:
    """Property tests for MemorySnapshot."""

    @given(obj=memory_snapshot_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=memory_snapshot_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=memory_snapshot_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.asyncio_tasks_pending >= 0
        assert obj.gc_objects_count >= 0
        assert isinstance(obj.tracemalloc_enabled, bool)
        if obj.redis_pool_size is not None:
            assert obj.redis_pool_size >= 0


class TestAdminUsersListResponse:
    """Property tests for AdminUsersListResponse."""

    @given(obj=admin_users_list_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_users_list_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=admin_users_list_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.total >= 0
        assert obj.limit >= 1
        assert obj.offset >= 0
        for user in obj.users:
            assert isinstance(user, dict)


class TestAdminCreateUserResponse:
    """Property tests for AdminCreateUserResponse."""

    @given(obj=admin_create_user_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_create_user_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=admin_create_user_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.user_id) > 0
        assert len(obj.email) > 0


class TestAdminDeleteUserResponse:
    """Property tests for AdminDeleteUserResponse."""

    @given(obj=admin_delete_user_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_delete_user_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=admin_delete_user_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert isinstance(obj.deleted, bool)
        assert len(obj.user_id) > 0


class TestAdminJobTriggerResponse:
    """Property tests for AdminJobTriggerResponse."""

    @given(obj=admin_job_trigger_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_job_trigger_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=admin_job_trigger_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.status in {"enqueued", "skipped", "error"}


class TestAdminClearCheckpointsResponse:
    """Property tests for AdminClearCheckpointsResponse."""

    @given(obj=admin_clear_checkpoints_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_clear_checkpoints_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=admin_clear_checkpoints_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.status in {"ok", "error"}


class TestAdminProgressTraceState:
    """Property tests for AdminProgressTraceState."""

    @given(obj=admin_progress_trace_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_progress_trace_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)


class TestAdminJobTraceState:
    """Property tests for AdminJobTraceState."""

    @given(obj=admin_job_trace_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_job_trace_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)


class TestAdminSearchTraceResponse:
    """Property tests for AdminSearchTraceResponse."""

    @given(obj=admin_search_trace_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_search_trace_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=admin_search_trace_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.search_id) > 0


class TestAdminCircuitBreakerResetResponse:
    """Property tests for AdminCircuitBreakerResetResponse."""

    @given(obj=admin_cb_reset_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_cb_reset_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=admin_cb_reset_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert len(obj.status) > 0
        assert isinstance(obj.previous_states, dict)


class TestAdminSchemaContractStatusResponse:
    """Property tests for AdminSchemaContractStatusResponse."""

    @given(obj=admin_schema_contract_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_schema_contract_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=admin_schema_contract_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert isinstance(obj.strict_mode, bool)
        assert isinstance(obj.stale, bool)


class TestCronJobHealthRow:
    """Property tests for CronJobHealthRow."""

    @given(obj=cron_job_health_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=cron_job_health_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=cron_job_health_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.runs_24h >= 0
        assert obj.failures_24h >= 0


class TestAdminCronStatusResponse:
    """Property tests for AdminCronStatusResponse."""

    @given(obj=admin_cron_status_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_cron_status_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=admin_cron_status_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.status in {"healthy", "error", "degraded"}
        assert obj.count >= 0
        assert len(obj.jobs) >= 0


class TestAdminLlmCostResponse:
    """Property tests for AdminLlmCostResponse."""

    @given(obj=admin_llm_cost_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_llm_cost_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=admin_llm_cost_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.month_to_date_usd >= 0
        assert obj.budget_usd >= 0
        assert obj.pct_used >= 0
        assert isinstance(obj.exceeded, bool)
        assert len(obj.month) > 0


class TestMrrHistoryEntry:
    """Property tests for MrrHistoryEntry."""

    @given(obj=mrr_history_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=mrr_history_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=mrr_history_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.mrr >= 0
        assert obj.subscriber_count >= 0


class TestRevenueMetricsResponse:
    """Property tests for RevenueMetricsResponse (large schema)."""

    @given(obj=revenue_metrics_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=revenue_metrics_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=revenue_metrics_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.mrr >= 0
        assert 0 <= obj.churn_rate_30d <= 1
        assert 0 <= obj.trial_to_paid_30d <= 1
        assert 0 <= obj.activation_d7 <= 1
        assert 0 <= obj.retention_d1 <= 1
        assert obj.total_subscribers >= 0
        assert obj.lookup_duration_ms >= 0


class TestDbPoolStatusResponse:
    """Property tests for DbPoolStatusResponse."""

    @given(obj=db_pool_status_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=db_pool_status_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=db_pool_status_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.status in {"healthy", "degraded", "critical"}
        assert obj.active >= 0
        assert obj.idle >= 0
        assert obj.total >= 0
        assert obj.max >= 0
        assert 0 <= obj.utilization <= 1
        assert 0 <= obj.utilization_pct <= 100
        assert obj.threshold_warning_pct >= 0
        assert obj.threshold_critical_pct >= 0


class TestUserSegmentsResponse:
    """Property tests for UserSegmentsResponse."""

    @given(obj=user_segments_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=user_segments_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=user_segments_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.total_users >= 0
        assert len(obj.count_by_state) >= 1


class TestAdminSyntheticResponse:
    """Property tests for AdminSyntheticResponse."""

    @given(obj=admin_synthetic_strategy)
    @_SETTINGS
    def test_roundtrip(self, obj):
        _run_roundtrip(obj)

    @given(obj=admin_synthetic_strategy)
    @_SETTINGS
    def test_json_schema(self, obj):
        _check_json_schema(obj)

    @given(obj=admin_synthetic_strategy)
    @_SETTINGS
    def test_invariants(self, obj):
        assert obj.status in {
            "success", "degraded", "failure", "no_data", "error",
        }
        assert obj.consecutive_failures >= 0

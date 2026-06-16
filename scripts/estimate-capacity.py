#!/usr/bin/env python3
"""
Capacity Estimator — SmartLic Growth Projections

Calcula projecoes de capacidade baseadas no numero de usuarios ativos.
Combina dados de load testing (k6, #1796), custos operacionais conhecidos,
e limites de infraestrutura para projetar quando e como escalar.

Uso:
    python scripts/estimate-capacity.py                    # Tabela para 100/500/1000/5000 users
    python scripts/estimate-capacity.py --users 250        # Projecao para numero especifico
    python scripts/estimate-capacity.py --json             # Saida JSON (pipeavel)
    python scripts/estimate-capacity.py --bottleneck       # Apenas bottleneck primario
    python scripts/estimate-capacity.py --brl              # Custos em reais (BRL)
    python scripts/estimate-capacity.py --exchange-rate 6.0  # Cambio customizado USD->BRL

Referencia:
    docs/operations/capacity-planning.md  — Documento completo de capacity planning
    docs/operations/capacity-limits.md    — Limites conhecidos e gargalos
    docs/operations/cost-analysis.md      — Custos operacionais detalhados
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field, asdict
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Constants — based on current infrastructure measurements
# ---------------------------------------------------------------------------

# Railway: current Pro plan (1 web + 1 worker + 1 frontend)
# These are measured/known values from production monitoring
CURRENT_WEB_VCPU = 0.5       # vCPU per web instance
CURRENT_WEB_RAM_GB = 0.5     # GB RAM per web instance
CURRENT_WORKER_VCPU = 0.25   # vCPU per ARQ worker
CURRENT_WORKER_RAM_GB = 0.25 # GB RAM per ARQ worker
CURRENT_FRONTEND_VCPU = 0.5  # vCPU per frontend instance
CURRENT_FRONTEND_RAM_GB = 0.5

# Railway pricing (USD) — as of 2026-06
RAILWAY_VCPU_PRICE = 20.00   # $/vCPU/month
RAILWAY_RAM_PRICE = 10.00    # $/GB/month
RAILWAY_PRO_FEE = 20.00      # $/month Pro plan base fee

# Supabase
SUPABASE_PRO_MONTHLY = 25.00  # $/month
SUPABASE_PRO_DB_GB = 8        # GB included
SUPABASE_OVERAGE_DB_GB = 0.125  # $/GB/month extra

# Upstash Redis
REDIS_FREE_COMMANDS = 500_000   # commands/month free tier
REDIS_PAID_PER_100K = 0.20      # $/100K commands above free

# Exchange rate (USD to BRL)
DEFAULT_EXCHANGE_RATE = 5.80    # Updated 2026-06 — reference from cost-analysis.md

# OpenAI GPT-4.1-nano
LLM_COST_PER_SEARCH = 0.000303  # $/search (from cost-analysis.md)

# Usage patterns (measured from analytics / engineering estimates)
SEARCHES_PER_USER_PER_DAY = {  # Active users → avg searches/day
    "light": 3,    # Power users doing daily monitoring
    "typical": 1,  # Regular weekly users
    "trial": 0.5,  # Trial / occasional users
}

# Profile mix assumption: 10% light, 40% typical, 50% trial
USER_PROFILE_MIX = {"light": 0.10, "typical": 0.40, "trial": 0.50}

# DB rows per search (from ingestion pipeline: results stored + cached)
DB_ROWS_PER_SEARCH = 500  # Average results returned per search

# Redis memory per search result (estimated from cache entries)
REDIS_BYTES_PER_RESULT = 2048  # ~2KB per cached result

# Current known limits (from capacity-limits.md and k6 #1796)
CURRENT_MAX_CONCURRENT_USERS = 30   # Measured: ~30 with 1 web worker
CURRENT_MAX_RPS = 5                  # Measured: ~5 req/s sustained
CURRENT_SEARCH_P95_MS = 8000         # ~8s p95 at capacity

# Throughput scaling factor per additional web worker
THROUGHPUT_PER_WORKER = 25  # Additional concurrent users per worker


# ---------------------------------------------------------------------------
# Projection model
# ---------------------------------------------------------------------------


@dataclass
class InfrastructureTier:
    """Represents an infrastructure configuration at a given scale."""

    name: str
    web_instances: int
    web_vcpu: float
    web_ram_gb: float
    worker_instances: int
    worker_vcpu: float
    worker_ram_gb: float
    frontend_instances: int
    supabase_tier: str           # "free" | "pro" | "pro+extra"
    redis_tier: str              # "free" | "paid"
    max_concurrent_users: int    # Estimated capacity
    notes: List[str] = field(default_factory=list)

    @property
    def total_vcpu(self) -> float:
        return (
            self.web_instances * self.web_vcpu
            + self.worker_instances * self.worker_vcpu
            + self.frontend_instances * CURRENT_FRONTEND_VCPU
        )

    @property
    def total_ram_gb(self) -> float:
        return (
            self.web_instances * self.web_ram_gb
            + self.worker_instances * self.worker_ram_gb
            + self.frontend_instances * CURRENT_FRONTEND_RAM_GB
        )


@dataclass
class CapacityProjection:
    """Full capacity projection for a given user count."""

    active_users: int
    searches_per_day: float
    searches_per_month: float
    concurrent_peak: int       # Estimated peak concurrent users
    db_rows_per_month: int
    redis_memory_mb: float
    redis_commands_per_month: int
    llm_cost_monthly_usd: float
    railway_cost_monthly_usd: float
    supabase_cost_monthly_usd: float
    redis_cost_monthly_usd: float
    total_cost_monthly_usd: float
    infrastructure_tier: InfrastructureTier
    bottleneck: str
    bottleneck_threshold_pct: float
    scale_action: str


def estimate_searches(
    active_users: int,
) -> Tuple[float, float]:
    """Estimate searches per day and per month.

    Uses weighted profile mix: 10% light (3/day), 40% typical (1/day), 50% trial (0.5/day).
    """
    weighted_searches = (
        USER_PROFILE_MIX["light"] * SEARCHES_PER_USER_PER_DAY["light"]
        + USER_PROFILE_MIX["typical"] * SEARCHES_PER_USER_PER_DAY["typical"]
        + USER_PROFILE_MIX["trial"] * SEARCHES_PER_USER_PER_DAY["trial"]
    )
    searches_day = active_users * weighted_searches
    searches_month = searches_day * 30
    return searches_day, searches_month


def estimate_concurrent_peak(active_users: int) -> int:
    """Estimate peak concurrent users (20% of active users during business hours)."""
    return max(1, int(active_users * 0.2))


def estimate_db_rows(searches_month: float) -> int:
    """Estimate new DB rows per month from search results."""
    return int(searches_month * DB_ROWS_PER_SEARCH)


def estimate_redis_memory(searches_day: float) -> float:
    """Estimate Redis memory needed for active cache entries (24h TTL)."""
    # Cache stores last 24h of search results
    return (searches_day * DB_ROWS_PER_SEARCH * REDIS_BYTES_PER_RESULT) / (1024 * 1024)


def estimate_redis_commands(searches_month: float) -> int:
    """Estimate Redis commands per month (see cost-analysis.md: ~12 cmd/search)."""
    return int(searches_month * 12)


def compute_infrastructure_tier(
    concurrent_peak: int,
) -> InfrastructureTier:
    """Determine the appropriate infrastructure tier for a given load level."""

    if concurrent_peak <= 30:
        return InfrastructureTier(
            name="Hobby/Pro Starter",
            web_instances=1,
            web_vcpu=0.5,
            web_ram_gb=0.5,
            worker_instances=1,
            worker_vcpu=0.25,
            worker_ram_gb=0.25,
            frontend_instances=1,
            supabase_tier="free",
            redis_tier="free",
            max_concurrent_users=30,
            notes=["1 Gunicorn worker (WEB_CONCURRENCY=1)", "Single web instance"],
        )

    if concurrent_peak <= 100:
        return InfrastructureTier(
            name="Pro — Single Instance",
            web_instances=1,
            web_vcpu=1.0,
            web_ram_gb=2.0,
            worker_instances=1,
            worker_vcpu=0.5,
            worker_ram_gb=0.5,
            frontend_instances=1,
            supabase_tier="pro",
            redis_tier="free",
            max_concurrent_users=100,
            notes=[
                "2-3 Gunicorn workers",
                "Redis required for SSE progress sharing",
                "Monitor ThreadPoolExecutor contention",
            ],
        )

    if concurrent_peak <= 300:
        return InfrastructureTier(
            name="Pro — Multi Instance",
            web_instances=2,
            web_vcpu=1.0,
            web_ram_gb=1.0,
            worker_instances=1,
            worker_vcpu=0.5,
            worker_ram_gb=0.5,
            frontend_instances=1,
            supabase_tier="pro",
            redis_tier="paid",
            max_concurrent_users=300,
            notes=[
                "Load-balanced web (2 instances)",
                "Gunicorn WEB_CONCURRENCY=3 per instance",
                "Redis Pub/Sub for SSE progress",
                "Supabase connection pooler (PgBouncer)",
            ],
        )

    if concurrent_peak <= 1000:
        return InfrastructureTier(
            name="Team — Horizontal Scale",
            web_instances=3,
            web_vcpu=1.0,
            web_ram_gb=2.0,
            worker_instances=2,
            worker_vcpu=1.0,
            worker_ram_gb=1.0,
            frontend_instances=2,
            supabase_tier="pro+extra",
            redis_tier="paid",
            max_concurrent_users=1000,
            notes=[
                "3 web instances behind load balancer",
                "Gunicorn workers tuned (4-6 per instance)",
                "Redis cluster for HA",
                "Supabase PgBouncer + connection pooling",
                "CDN for frontend assets",
                "LLM batch processing queue",
            ],
        )

    # 1000+ concurrent peak — enterprise
    return InfrastructureTier(
        name="Enterprise — Fully Distributed",
        web_instances=5,
        web_vcpu=2.0,
        web_ram_gb=4.0,
        worker_instances=3,
        worker_vcpu=2.0,
        worker_ram_gb=4.0,
        frontend_instances=2,
        supabase_tier="pro+extra",
        redis_tier="paid",
        max_concurrent_users=3000,
        notes=[
            "Auto-scaling web pool",
            "Dedicated Redis cluster (Upstash Pro/Hobby)",
            "Partitioned worker queues by source",
            "Supabase read replicas",
            "Full observability stack (Grafana Cloud)",
        ],
    )


def identify_bottleneck(
    concurrent_peak: int,
    infra: InfrastructureTier,
    searches_month: float,
    redis_memory_mb: float,
    redis_commands_per_month: int,
) -> Tuple[str, float, str]:
    """Identify the primary bottleneck and suggested action.

    Returns:
        (bottleneck_name, threshold_pct, action_description)
    """

    # 1. Gunicorn worker capacity
    if concurrent_peak > CURRENT_MAX_CONCURRENT_USERS:
        workers_needed = max(1, math.ceil(concurrent_peak / THROUGHPUT_PER_WORKER))
        capacity_pct = (infra.web_instances * THROUGHPUT_PER_WORKER) / concurrent_peak * 100
        if capacity_pct < 100:
            return (
                "Gunicorn workers — WEB_CONCURRENCY limit",
                round(100 - capacity_pct, 1),
                f"Increase WEB_CONCURRENCY to {workers_needed} or add web instances",
            )

    # 2. Redis memory (Upstash free tier: 256MB)
    if redis_memory_mb > 200:
        return (
            "Redis memory — cache eviction risk",
            round(redis_memory_mb / 256 * 100, 1),
            "Upgrade Redis to paid tier or reduce cache TTL",
        )

    # 3. Redis commands (free tier: 500K/month)
    if redis_commands_per_month > 400_000:
        cmd_pct = redis_commands_per_month / REDIS_FREE_COMMANDS * 100
        return (
            "Redis command quota — free tier limit",
            round(cmd_pct, 1),
            "Upgrade to Upstash paid tier (pay-as-you-go)",
        )

    # 4. Supabase storage
    # Estimate: ~512 bytes per DB row (metadata + JSON results)
    DB_BYTES_PER_ROW = 512
    db_gb_per_month = (DB_ROWS_PER_SEARCH * searches_month * DB_BYTES_PER_ROW) / (1024**3)
    if db_gb_per_month > 6:  # 8GB - buffer
        return (
            "Supabase DB storage — approaching Pro limit",
            round(db_gb_per_month / SUPABASE_PRO_DB_GB * 100, 1),
            "Monitor DB size, consider data retention cleanup or upgrade",
        )

    # 5. ThreadPoolExecutor / LLM calls
    if concurrent_peak > 50:
        return (
            "LLM ThreadPoolExecutor contention",
            0.0,
            "Implement LLM call batching, increase max_workers proportionally",
        )

    # Default: all within limits
    return (
        "None — within current capacity",
        0.0,
        "Continue monitoring",
    )


def compute_railway_cost(infra: InfrastructureTier) -> float:
    """Compute monthly Railway cost in USD."""
    compute_cost = (
        infra.web_instances * (infra.web_vcpu * RAILWAY_VCPU_PRICE + infra.web_ram_gb * RAILWAY_RAM_PRICE)
        + infra.worker_instances * (infra.worker_vcpu * RAILWAY_VCPU_PRICE + infra.worker_ram_gb * RAILWAY_RAM_PRICE)
        + infra.frontend_instances * (CURRENT_FRONTEND_VCPU * RAILWAY_VCPU_PRICE + CURRENT_FRONTEND_RAM_GB * RAILWAY_RAM_PRICE)
    )
    return compute_cost + RAILWAY_PRO_FEE


def compute_supabase_cost(infra: InfrastructureTier, db_rows_month: int) -> float:
    """Compute monthly Supabase cost in USD."""
    base = 0.0
    if infra.supabase_tier == "pro":
        base = SUPABASE_PRO_MONTHLY
    elif infra.supabase_tier == "pro+extra":
        base = SUPABASE_PRO_MONTHLY
        # Estimate extra storage beyond 8GB
        DB_BYTES_PER_ROW = 512
        estimated_gb = (db_rows_month * DB_BYTES_PER_ROW) / (1024**3)
        if estimated_gb > SUPABASE_PRO_DB_GB:
            extra = estimated_gb - SUPABASE_PRO_DB_GB
            base += extra * SUPABASE_OVERAGE_DB_GB
    return round(base, 2)


def compute_redis_cost(infra: InfrastructureTier, commands_month: int) -> float:
    """Compute monthly Redis cost in USD."""
    if infra.redis_tier == "free" and commands_month <= REDIS_FREE_COMMANDS:
        return 0.0
    # Pay-as-you-go beyond free quota
    additional_commands = max(0, commands_month - REDIS_FREE_COMMANDS)
    cost = (additional_commands / 100_000) * REDIS_PAID_PER_100K
    return max(0.0, round(cost, 2))


def estimate_llm_cost(searches_month: float) -> float:
    """Compute monthly LLM cost in USD."""
    return round(searches_month * LLM_COST_PER_SEARCH, 2)


# ---------------------------------------------------------------------------
# Projection runner
# ---------------------------------------------------------------------------


def project(active_users: int) -> CapacityProjection:
    """Generate a full capacity projection for a given number of active users."""
    searches_day, searches_month = estimate_searches(active_users)
    concurrent_peak = estimate_concurrent_peak(active_users)
    db_rows_month = estimate_db_rows(searches_month)
    redis_memory_mb = estimate_redis_memory(searches_day)
    redis_commands_per_month = estimate_redis_commands(searches_month)

    infra = compute_infrastructure_tier(concurrent_peak)

    railway_cost = compute_railway_cost(infra)
    supabase_cost = compute_supabase_cost(infra, db_rows_month)
    redis_cost = compute_redis_cost(infra, redis_commands_per_month)
    llm_cost = estimate_llm_cost(searches_month)

    total_cost = round(railway_cost + supabase_cost + redis_cost + llm_cost, 2)

    bottleneck, threshold, action = identify_bottleneck(
        concurrent_peak, infra, searches_month, redis_memory_mb, redis_commands_per_month
    )

    return CapacityProjection(
        active_users=active_users,
        searches_per_day=round(searches_day, 1),
        searches_per_month=round(searches_month, 1),
        concurrent_peak=concurrent_peak,
        db_rows_per_month=db_rows_month,
        redis_memory_mb=round(redis_memory_mb, 1),
        redis_commands_per_month=redis_commands_per_month,
        llm_cost_monthly_usd=llm_cost,
        railway_cost_monthly_usd=railway_cost,
        supabase_cost_monthly_usd=supabase_cost,
        redis_cost_monthly_usd=redis_cost,
        total_cost_monthly_usd=total_cost,
        infrastructure_tier=infra,
        bottleneck=bottleneck,
        bottleneck_threshold_pct=threshold,
        scale_action=action,
    )


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def print_projection_table(
    projections: List[CapacityProjection],
    exchange_rate: float | None = None,
) -> None:
    """Print projections as a readable ASCII table.

    If exchange_rate is provided, costs are shown in BRL (R$) as well.
    """
    currency_symbol = "R$" if exchange_rate else "$"
    rate_note = f" (cambio: USD 1 = BRL {exchange_rate})" if exchange_rate else ""

    header = (
        f"{'Users':>8} | {'Searches/mo':>12} | {'Peak conc.':>10} | {'Redis MB':>8} | "
        f"{'Infra Tier':<25} | {'Total/mo':>10} | {'Bottleneck':<40}"
    )
    sep = "-" * len(header)

    title = "SmartLic — Capacity Projections (2026-06-15)"
    if exchange_rate:
        title += f"  [BRL{rate_note}]"
    print(f"\n{title}\n")
    print(header)
    print(sep)

    def fmt_cost(usd: float) -> str:
        if exchange_rate:
            return f"R$ {usd * exchange_rate:>8.2f}"
        return f"${usd:>8.2f}"

    for p in projections:
        print(
            f"{p.active_users:>8} | {int(p.searches_per_month):>12,} | {p.concurrent_peak:>10} | "
            f"{p.redis_memory_mb:>8.1f} | {p.infrastructure_tier.name:<25} | "
            f"{fmt_cost(p.total_cost_monthly_usd)} | {p.bottleneck:<40}"
        )

    print(sep)
    print()

    # Detailed view per tier
    for p in projections:
        currency = "R$" if exchange_rate else "$"
        print(f"\n--- {p.active_users} Active Users ---")
        print(f"  Tier:                {p.infrastructure_tier.name}")
        print(f"  Searches/day:        {int(p.searches_per_day):,}")
        print(f"  Searches/month:      {int(p.searches_per_month):,}")
        print(f"  Peak concurrent:     {p.concurrent_peak}")
        print(f"  DB rows/month:       {p.db_rows_per_month:,}")
        print(f"  Redis memory:        {p.redis_memory_mb:.1f} MB")
        print(f"  Redis commands/mo:   {p.redis_commands_per_month:,}")
        print("  Cost breakdown:")
        f_rail = p.railway_cost_monthly_usd * exchange_rate if exchange_rate else p.railway_cost_monthly_usd
        f_supa = p.supabase_cost_monthly_usd * exchange_rate if exchange_rate else p.supabase_cost_monthly_usd
        f_redis = p.redis_cost_monthly_usd * exchange_rate if exchange_rate else p.redis_cost_monthly_usd
        f_llm = p.llm_cost_monthly_usd * exchange_rate if exchange_rate else p.llm_cost_monthly_usd
        f_total = p.total_cost_monthly_usd * exchange_rate if exchange_rate else p.total_cost_monthly_usd
        print(f"    Railway:           {currency} {f_rail:.2f}/mo")
        print(f"    Supabase:          {currency} {f_supa:.2f}/mo")
        print(f"    Redis:             {currency} {f_redis:.2f}/mo")
        print(f"    LLM (OpenAI):      {currency} {f_llm:.2f}/mo")
        print(f"    Total:             {currency} {f_total:.2f}/mo")
        print(f"  Primary bottleneck:  {p.bottleneck}")
        if p.bottleneck_threshold_pct > 0:
            print(f"  Threshold:           {p.bottleneck_threshold_pct:.1f}% of limit")
        print(f"  Recommended action:  {p.scale_action}")
        if p.infrastructure_tier.notes:
            print("  Notes:")
            for note in p.infrastructure_tier.notes:
                print(f"    - {note}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SmartLic Capacity Planner — projeta necessidades de infraestrutura."
    )
    parser.add_argument(
        "--users", type=int, nargs="+", default=[100, 500, 1000, 5000],
        help="Numero(s) de usuarios ativos para projetar (default: 100 500 1000 5000)",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Saida em JSON (pipeavel)",
    )
    parser.add_argument(
        "--bottleneck", action="store_true",
        help="Exibe apenas o bottleneck primario para o cenario",
    )
    parser.add_argument(
        "--brl", action="store_true",
        help="Exibe custos em reais (BRL) usando cambio padrao (USD 1 = BRL {})".format(DEFAULT_EXCHANGE_RATE),
    )
    parser.add_argument(
        "--exchange-rate", type=float, default=None,
        help="Taxa de cambio USD->BRL customizada (ex: 6.0). Implica --brl.",
    )
    args = parser.parse_args()

    projections = [project(u) for u in args.users]

    # Determine exchange rate for BRL output
    exchange_rate = args.exchange_rate
    if args.brl and exchange_rate is None:
        exchange_rate = DEFAULT_EXCHANGE_RATE

    if args.json:
        output = []
        for p in projections:
            d = asdict(p)
            if exchange_rate:
                d["exchange_rate"] = exchange_rate
                d["total_cost_monthly_brl"] = round(p.total_cost_monthly_usd * exchange_rate, 2)
                d["railway_cost_monthly_brl"] = round(p.railway_cost_monthly_usd * exchange_rate, 2)
                d["supabase_cost_monthly_brl"] = round(p.supabase_cost_monthly_usd * exchange_rate, 2)
                d["redis_cost_monthly_brl"] = round(p.redis_cost_monthly_usd * exchange_rate, 2)
                d["llm_cost_monthly_brl"] = round(p.llm_cost_monthly_usd * exchange_rate, 2)
            d["infrastructure_tier"] = {
                "name": p.infrastructure_tier.name,
                "web_instances": p.infrastructure_tier.web_instances,
                "worker_instances": p.infrastructure_tier.worker_instances,
                "web_vcpu": p.infrastructure_tier.web_vcpu,
                "web_ram_gb": p.infrastructure_tier.web_ram_gb,
                "supabase_tier": p.infrastructure_tier.supabase_tier,
                "redis_tier": p.infrastructure_tier.redis_tier,
            }
            output.append(d)
        print(json.dumps(output, indent=2))
        return

    if args.bottleneck:
        for p in projections:
            print(f"{p.active_users:>6} users | {p.bottleneck} ({p.bottleneck_threshold_pct:.0f}%) | {p.scale_action}")
        return

    print_projection_table(projections, exchange_rate=exchange_rate)


if __name__ == "__main__":
    main()

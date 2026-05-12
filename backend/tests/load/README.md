# Backend Load Tests — Stage Pattern Reproducers

Locust scenarios reproduzem padrões de saturação observados em prod.

## Stage 4-7 Pattern (`stage_4_7_pattern.py`)

Reproduz wedge backend 2026-04-27 a 29:
- SSG burst (31 workers, weight=5)
- Googlebot crawl (weight=4)
- Health probe (weight=1, monitoring)

### Local smoke
```bash
pip install locust==2.32.0
cd backend/tests/load
locust -f stage_4_7_pattern.py --host http://localhost:8000 --users 5 --run-time 30s --headless
```

### Weekly CI
Workflow `.github/workflows/load-test-weekly.yml` cron Sun 08:00 UTC contra `https://api.smartlic.tech` (OPS-RELIABILITY-002).

### Thresholds (OPS-RELIABILITY-002)
- p95 latency: <500ms
- error_rate: <1%

Falha CI publica Sentry alert + PR comment (manual dispatch only).

### Environment Variables
- `LOCUST_HOST` — Target API URL (default: `https://api.smartlic.tech`)
- `SUPABASE_ANON_KEY` — Required for authenticated endpoints (`/v1/buscar`, `/v1/user/profile`)

### Running with authenticated endpoints
```bash
LOCUST_HOST=https://api.smartlic.tech SUPABASE_ANON_KEY=your_key_here \
  locust -f stage_4_7_pattern.py --host "$LOCUST_HOST" --users 10 --run-time 60s --headless
```

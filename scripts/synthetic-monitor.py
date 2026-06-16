#!/usr/bin/env python3
"""Issue #1869 — Synthetic monitoring CLI (standalone).

Executes the complete user flow via the SmartLic API and reports
per-stage latencies.  Intended for manual debugging / ad-hoc checks;
the persistent ARQ cron job is in ``backend/jobs/cron/synthetic_monitor.py``.

Usage:
    python scripts/synthetic-monitor.py
    python scripts/synthetic-monitor.py --base-url https://api.smartlic.tech
    python scripts/synthetic-monitor.py --json  # machine-readable output

Environment variables (same as the ARQ cron job):
    SYNTHETIC_MONITOR_EMAIL      — test user email
    SYNTHETIC_MONITOR_PASSWORD   — test user password
    API_BASE_URL                 — backend base URL (default: https://api.smartlic.tech)
    SUPABASE_URL                 — Supabase project URL for auth
    SUPABASE_ANON_KEY            — Supabase anon key for auth
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time as time_mod


def _get_config(key: str, default: str = "") -> str:
    return os.getenv(key, default)


async def _async_main(base_url: str, output_json: bool) -> int:
    """Run the monitor and print results."""
    # Import httpx here so the script is importable without it installed
    import httpx

    supabase_url = _get_config("SUPABASE_URL", "").rstrip("/")
    anon_key = _get_config("SUPABASE_ANON_KEY", "")
    email = _get_config("SYNTHETIC_MONITOR_EMAIL", "")
    password = _get_config("SYNTHETIC_MONITOR_PASSWORD", "")

    if not email or not password:
        print("ERROR: SYNTHETIC_MONITOR_EMAIL and SYNTHETIC_MONITOR_PASSWORD must be set")
        return 1

    if not supabase_url or not anon_key:
        print("ERROR: SUPABASE_URL and SUPABASE_ANON_KEY must be set")
        return 1

    stages = {}
    overall_start = time_mod.monotonic()

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0)) as client:
        # Auth
        ts = time_mod.monotonic()
        try:
            auth_resp = await client.post(
                f"{supabase_url}/auth/v1/token?grant_type=password",
                headers={"apikey": anon_key, "Content-Type": "application/json"},
                json={"email": email, "password": password},
            )
            auth_resp.raise_for_status()
            auth_data = auth_resp.json()
            access_token = auth_data.get("access_token", "")
            stages["auth"] = {
                "elapsed_ms": int((time_mod.monotonic() - ts) * 1000),
                "success": bool(access_token),
            }
            if not access_token:
                stages["auth"]["error"] = "no access_token"
        except Exception as e:
            stages["auth"] = {"elapsed_ms": int((time_mod.monotonic() - ts) * 1000), "success": False, "error": str(e)}

        if not stages.get("auth", {}).get("success"):
            print("AUTH FAILED — cannot proceed")
            if output_json:
                print(json.dumps({"status": "failure", "stages": stages}))
            return 1

        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        # Busca
        ts = time_mod.monotonic()
        try:
            search_resp = await client.post(
                f"{base_url}/v1/buscar",
                headers=headers,
                json={"termo": "informatica", "ufs": ["SP"], "modalidades": ["pregao"]},
                timeout=httpx.Timeout(30.0),
            )
            stages["search"] = {
                "elapsed_ms": int((time_mod.monotonic() - ts) * 1000),
                "success": search_resp.status_code in (200, 202),
                "http_status": search_resp.status_code,
            }
            if search_resp.status_code not in (200, 202):
                stages["search"]["error"] = search_resp.text[:200]

            search_data = search_resp.json() if search_resp.status_code in (200, 202) else {}

            # Poll if async
            if search_resp.status_code == 202:
                search_id = search_data.get("search_id", "")
                poll_deadline = time_mod.monotonic() + 30
                while time_mod.monotonic() < poll_deadline:
                    await asyncio_sleep(2)
                    status_resp = await client.get(f"{base_url}/v1/search/{search_id}/status", headers=headers)
                    if status_resp.status_code == 200:
                        state = status_resp.json().get("state", "")
                        if state in ("completed", "complete"):
                            stages["search"]["elapsed_ms"] = int((time_mod.monotonic() - ts) * 1000)
                            break
                        elif state in ("error", "failed"):
                            stages["search"]["success"] = False
                            stages["search"]["state"] = state
                            break
        except Exception as e:
            stages["search"] = {"elapsed_ms": int((time_mod.monotonic() - ts) * 1000), "success": False, "error": str(e)}

        # Results
        if stages.get("search", {}).get("success"):
            search_id = search_data.get("search_id", "")
            ts = time_mod.monotonic()
            try:
                results_resp = await client.get(f"{base_url}/v1/search/{search_id}/results", headers=headers)
                if results_resp.status_code == 200:
                    results_data = results_resp.json()
                    total_bids = 0
                    if isinstance(results_data, dict):
                        total_bids = results_data.get("total_bids", 0) or results_data.get("total_results", 0) or len(results_data.get("results", []) or [])
                    elif isinstance(results_data, list):
                        total_bids = len(results_data)
                    stages["results"] = {
                        "elapsed_ms": int((time_mod.monotonic() - ts) * 1000),
                        "success": total_bids > 0,
                        "total_bids": total_bids,
                    }

                    # Viability
                    if total_bids > 0:
                        first_bid = results_data.get("results", [{}])[0] if isinstance(results_data, dict) else (results_data[0] if results_data else {})
                        viability = first_bid.get("viability_score") or first_bid.get("viability") or first_bid.get("viabilidade") if isinstance(first_bid, dict) else None
                    else:
                        viability = None
                    stages["viability"] = {
                        "elapsed_ms": int((time_mod.monotonic() - ts) * 1000),
                        "success": viability is not None,
                    }

                    # Excel
                    excel_url = results_data.get("excel_url") or results_data.get("relatorio_url") if isinstance(results_data, dict) else None
                    stages["excel"] = {
                        "elapsed_ms": int((time_mod.monotonic() - ts) * 1000),
                        "success": bool(excel_url),
                    }
                else:
                    stages["results"] = {"elapsed_ms": int((time_mod.monotonic() - ts) * 1000), "success": False, "error": f"HTTP {results_resp.status_code}"}
            except Exception as e:
                stages["results"] = {"elapsed_ms": int((time_mod.monotonic() - ts) * 1000), "success": False, "error": str(e)}

    overall_elapsed = int((time_mod.monotonic() - overall_start) * 1000)
    all_success = all(s.get("success") for s in stages.values())
    status = "success" if all_success else "failure"

    result = {
        "status": status,
        "overall_elapsed_ms": overall_elapsed,
        "stages": stages,
        "timings": {k: v.get("elapsed_ms", 0) for k, v in stages.items()},
    }

    if output_json:
        print(json.dumps(result, default=str))
    else:
        print(f"\nSynthetic Monitor Results ({status})")
        print(f"{'='*50}")
        print(f"Overall: {overall_elapsed}ms")
        for stage, data in stages.items():
            mark = "OK" if data.get("success") else "FAIL"
            extra = f" — {data.get('error', '')}" if data.get("error") else ""
            print(f"  {stage:12s} {data.get('elapsed_ms', 0):>6}ms  [{mark}]{extra}")

    return 0 if all_success else 1


async def asyncio_sleep(seconds: float) -> None:
    import asyncio
    await asyncio.sleep(seconds)


def main() -> int:
    parser = argparse.ArgumentParser(description="Synthetic user-flow monitor")
    parser.add_argument("--base-url", default=_get_config("API_BASE_URL", "https://api.smartlic.tech"))
    parser.add_argument("--json", action="store_true", help="Output JSON instead of human-readable")
    args = parser.parse_args()

    import asyncio
    return asyncio.run(_async_main(args.base_url.rstrip("/"), args.json))


if __name__ == "__main__":
    sys.exit(main())

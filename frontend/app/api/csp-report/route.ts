/**
 * STORY-311 AC3: CSP violation report collection endpoint.
 * ISSUE-1798: Also receives report-only violation data from CSP-Report-Only header.
 *
 * Receives Content-Security-Policy violation reports from browsers.
 * Supports both legacy report-uri format and Reporting API v1 (report-to).
 * Handles both "enforce" and "report" dispositions — the disposition field
 * in the log output distinguishes which CSP header triggered the report.
 *
 * Rate limited to 100 reports/min per IP to prevent flood.
 */

import { NextRequest, NextResponse } from "next/server";

// In-memory rate limiter (persists across requests in Railway standalone mode)
const reportCounts = new Map<
  string,
  { count: number; resetAt: number }
>();
const MAX_REPORTS_PER_MIN = 100;

function isRateLimited(ip: string): boolean {
  const now = Date.now();
  const entry = reportCounts.get(ip);

  if (!entry || now > entry.resetAt) {
    reportCounts.set(ip, { count: 1, resetAt: now + 60_000 });
    return false;
  }

  entry.count++;
  if (entry.count > MAX_REPORTS_PER_MIN) {
    return true;
  }

  return false;
}

// Periodic cleanup to prevent memory leak (every 1000 checks)
let cleanupCounter = 0;
function maybeCleanup() {
  cleanupCounter++;
  if (cleanupCounter >= 1000) {
    cleanupCounter = 0;
    const now = Date.now();
    for (const [key, entry] of reportCounts) {
      if (now > entry.resetAt) {
        reportCounts.delete(key);
      }
    }
  }
}

export async function POST(request: NextRequest) {
  const ip =
    request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() ||
    "unknown";

  maybeCleanup();

  if (isRateLimited(ip)) {
    return NextResponse.json(
      { error: "Rate limit exceeded" },
      { status: 429 }
    );
  }

  try {
    const body = await request.json();

    // Legacy report-uri format wraps in "csp-report" key
    const report = body["csp-report"] || body;

    const violatedDirective =
      report["violated-directive"] ||
      report.violatedDirective ||
      report.effectiveDirective ||
      "unknown";
    const blockedUri =
      report["blocked-uri"] || report.blockedURL || "unknown";
    const documentUri =
      report["document-uri"] || report.documentURL || "unknown";
    const disposition = report.disposition || "enforce";

    // Structured log for observability (picked up by Railway log drain)
    console.log(
      JSON.stringify({
        type: "csp-violation",
        violated_directive: violatedDirective,
        blocked_uri: blockedUri,
        document_uri: documentUri,
        disposition,
        timestamp: new Date().toISOString(),
      })
    );

    return new NextResponse(null, { status: 204 });
  } catch {
    return NextResponse.json(
      { error: "Invalid report format" },
      { status: 400 }
    );
  }
}

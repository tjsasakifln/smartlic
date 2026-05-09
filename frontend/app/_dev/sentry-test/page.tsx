"use client";

/**
 * SMARTLIC-FE-F-INVEST-001 AC2 — Sentry Frontend Trigger Page (DEV-ONLY)
 *
 * Forced trigger to confirm SDK init + transport reaches Sentry dashboard.
 *
 * Production gate: page returns 404 in production builds. Only renders when
 * NODE_ENV !== "production" OR NEXT_PUBLIC_ENABLE_SENTRY_TEST="1".
 *
 * Usage:
 *   1. `cd frontend && npm run dev`
 *   2. Open http://localhost:3000/_dev/sentry-test
 *   3. Click "Throw runtime Error" — Sentry should capture (look in dashboard
 *      smartlic-frontend project; allow 30-60s for ingest).
 *   4. Click "useEffect mount-time error" — covers SSR/SSG hydration paths.
 *   5. Open browser devtools console: with `NEXT_PUBLIC_SENTRY_DEBUG=1`
 *      `[sentry-debug]` lines from `sentry.client.config.ts beforeSend`
 *      log every event the SDK considers, before filter rules apply.
 *
 * RCA (2026-05-08): proven empirically that Sentry SDK init + ingest works.
 * Real root cause is `beforeSend` over-filter + Sentry plan quota exhaustion.
 * See `docs/sessions/2026-05/2026-05-08-sentry-fe-quiescent-rca.md`.
 */

import { useEffect, useState } from "react";

const SHOULD_RENDER =
  process.env.NODE_ENV !== "production" ||
  process.env.NEXT_PUBLIC_ENABLE_SENTRY_TEST === "1";

export default function SentryTestPage() {
  const [mountErrorArmed, setMountErrorArmed] = useState(false);

  useEffect(() => {
    if (mountErrorArmed) {
      throw new Error("smartlic-fe-f-test:mount-time");
    }
  }, [mountErrorArmed]);

  if (!SHOULD_RENDER) {
    return (
      <main style={{ padding: "2rem", fontFamily: "system-ui" }}>
        <h1>Not available in production</h1>
        <p>
          Set <code>NEXT_PUBLIC_ENABLE_SENTRY_TEST=1</code> to enable the
          Sentry trigger page in a production-like build.
        </p>
      </main>
    );
  }

  return (
    <main style={{ padding: "2rem", fontFamily: "system-ui", maxWidth: 720 }}>
      <h1>Sentry Frontend Trigger (dev-only)</h1>
      <p>
        Story: <code>SMARTLIC-FE-F-INVEST-001</code> AC2. Forces a client-side
        error to confirm the Sentry SDK is initialized and the transport
        reaches the dashboard.
      </p>
      <p>
        Allow 30-60 seconds after triggering, then check the{" "}
        <code>smartlic-frontend</code> project on Sentry. If the issue does
        NOT appear, look at the browser devtools network tab for a request to{" "}
        <code>/monitoring</code> (the Sentry tunnel route configured in{" "}
        <code>next.config.js</code>).
      </p>
      <hr />
      <div style={{ display: "flex", gap: "1rem", flexWrap: "wrap" }}>
        <button
          type="button"
          onClick={() => {
            throw new Error("smartlic-fe-f-test:onclick");
          }}
          style={{
            padding: "0.75rem 1.5rem",
            background: "#dc2626",
            color: "white",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
          }}
        >
          Throw runtime Error (onClick)
        </button>
        <button
          type="button"
          onClick={() => setMountErrorArmed(true)}
          style={{
            padding: "0.75rem 1.5rem",
            background: "#7c3aed",
            color: "white",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
          }}
        >
          Arm useEffect mount-time error
        </button>
        <button
          type="button"
          onClick={() => {
            void Promise.reject(
              new Error("smartlic-fe-f-test:unhandled-rejection")
            );
          }}
          style={{
            padding: "0.75rem 1.5rem",
            background: "#0891b2",
            color: "white",
            border: "none",
            borderRadius: 6,
            cursor: "pointer",
          }}
        >
          Trigger unhandled Promise rejection
        </button>
      </div>
      <hr />
      <h2>Expected (post-fix)</h2>
      <ul>
        <li>
          Each click produces a Sentry issue tagged{" "}
          <code>smartlic-fe-f-test:*</code> within ~60s.
        </li>
        <li>
          Plan quota and <code>beforeSend</code> filter rules MUST allow these
          messages through. <code>beforeSend</code> drops only{" "}
          <code>USER_CANCELLED</code>, <code>NAVIGATION</code>,{" "}
          <code>AbortError</code>, and SSE pipe errors with{" "}
          <code>elapsed_ms &gt; 110000</code> &mdash; none match the test
          messages above.
        </li>
      </ul>
    </main>
  );
}

/**
 * STORY-300 + STORY-311: Security Headers Tests
 *
 * Tests CSP and security headers configuration.
 * Since Next.js middleware requires edge runtime APIs unavailable in jsdom,
 * we test the CSP policy content and next.config.js headers directly.
 *
 * STORY-300: Initial CSP + security headers
 * STORY-311: CSP enforcement, deduplication, new headers (COOP, HSTS preload)
 */

import fs from "fs";
import path from "path";

const middlewarePath = path.join(__dirname, "..", "middleware.ts");
const nextConfigPath = path.join(__dirname, "..", "next.config.js");

describe("STORY-311: Security Headers Configuration", () => {
  let middlewareSource: string;
  let nextConfigSource: string;

  beforeAll(() => {
    middlewareSource = fs.readFileSync(middlewarePath, "utf-8");
    nextConfigSource = fs.readFileSync(nextConfigPath, "utf-8");
  });

  describe("AC1: CSP enforcing mode in middleware.ts", () => {
    it("should define addSecurityHeaders function", () => {
      expect(middlewareSource).toContain("function addSecurityHeaders");
    });

    it("should use enforcing Content-Security-Policy (not Report-Only)", () => {
      // Must set Content-Security-Policy (enforcing)
      expect(middlewareSource).toContain(
        '"Content-Security-Policy"'
      );
    });

    it("should ALSO set CSP-Report-Only with nonce-based policy (ISSUE-1798 Phase 1)", () => {
      // ISSUE-1798 Phase 1: Report-Only header added alongside enforcing CSP.
      // The report-only policy removes 'unsafe-inline' from script-src and uses
      // a per-request nonce + SHA-256 hash for the theme-init script.
      // Phase 2: after 0 violations, replace enforcing CSP with nonce-based policy.
      expect(middlewareSource).toContain(
        "Content-Security-Policy-Report-Only"
      );
    });

    it("should include default-src 'self' directive", () => {
      expect(middlewareSource).toContain("default-src 'self'");
    });

    it("should include Stripe in script-src", () => {
      expect(middlewareSource).toContain("https://js.stripe.com");
    });

    it("should include Sentry CDN in script-src", () => {
      expect(middlewareSource).toContain("https://cdn.sentry.io");
    });

    it("should include Supabase in connect-src", () => {
      expect(middlewareSource).toContain("https://*.supabase.co");
    });

    it("should include Supabase WebSocket in connect-src", () => {
      expect(middlewareSource).toContain("wss://*.supabase.co");
    });

    it("should include Stripe API in connect-src", () => {
      expect(middlewareSource).toContain("https://api.stripe.com");
    });

    it("should include Sentry ingest in connect-src", () => {
      expect(middlewareSource).toContain("https://*.sentry.io");
    });

    it("should include Mixpanel in connect-src", () => {
      expect(middlewareSource).toContain("https://api-js.mixpanel.com");
      expect(middlewareSource).toContain("https://api.mixpanel.com");
    });

    it("should include Stripe in frame-src", () => {
      expect(middlewareSource).toContain("frame-src");
      expect(middlewareSource).toContain("https://js.stripe.com");
    });

    it("should block object-src", () => {
      expect(middlewareSource).toContain("object-src 'none'");
    });

    it("should restrict base-uri", () => {
      expect(middlewareSource).toContain("base-uri 'self'");
    });

    it("should apply headers to API routes", () => {
      expect(middlewareSource).toContain(
        'addSecurityHeaders(NextResponse.next())'
      );
    });

    it("should apply headers to public routes", () => {
      const publicRouteReturn = middlewareSource.includes(
        "return addSecurityHeaders(NextResponse.next())"
      );
      expect(publicRouteReturn).toBe(true);
    });

    it("should apply headers to authenticated route responses", () => {
      expect(middlewareSource).toContain(
        "return addSecurityHeaders(NextResponse.next({"
      );
    });
  });

  describe("AC2: CSP report-uri and report-to directives", () => {
    it("should include report-uri directive pointing to /api/csp-report", () => {
      expect(middlewareSource).toContain("report-uri /api/csp-report");
    });

    it("should include report-to directive", () => {
      expect(middlewareSource).toContain("report-to csp-endpoint");
    });

    it("should set Report-To header with group definition", () => {
      expect(middlewareSource).toContain("Report-To");
      expect(middlewareSource).toContain("csp-endpoint");
    });
  });

  describe("AC4: CSP whitelist completeness", () => {
    const requiredDirectives = [
      "default-src",
      "script-src",
      "style-src",
      "img-src",
      "font-src",
      "connect-src",
      "frame-src",
      "object-src",
      "base-uri",
    ];

    for (const directive of requiredDirectives) {
      it(`should have ${directive} directive`, () => {
        expect(middlewareSource).toContain(directive);
      });
    }
  });

  describe("AC5: Headers unified in middleware (no duplication)", () => {
    it("should NOT have Content-Security-Policy-Report-Only in next.config.js", () => {
      expect(nextConfigSource).not.toContain(
        "Content-Security-Policy-Report-Only"
      );
    });

    it("should NOT have X-Content-Type-Options in next.config.js headers()", () => {
      // next.config.js should not have the headers() function with security headers
      expect(nextConfigSource).not.toContain("'X-Content-Type-Options'");
    });

    it("should NOT have X-Frame-Options in next.config.js headers()", () => {
      expect(nextConfigSource).not.toContain("'X-Frame-Options'");
    });

    it("should reference AC5 deduplication comment", () => {
      expect(nextConfigSource).toContain("AC5");
    });
  });

  describe("AC6: Cross-Origin-Opener-Policy", () => {
    it("should set Cross-Origin-Opener-Policy: same-origin", () => {
      expect(middlewareSource).toContain("Cross-Origin-Opener-Policy");
      expect(middlewareSource).toContain("same-origin");
    });
  });

  describe("AC7: Cross-Origin-Embedder-Policy (skipped)", () => {
    it("should document why COEP is not enabled", () => {
      // COEP require-corp breaks Stripe iframe — documented in comment
      expect(middlewareSource).toContain("COEP");
      expect(middlewareSource).toContain("Stripe");
    });
  });

  describe("AC8: X-DNS-Prefetch-Control", () => {
    it("should set X-DNS-Prefetch-Control: off", () => {
      expect(middlewareSource).toContain("X-DNS-Prefetch-Control");
      expect(middlewareSource).toContain("off");
    });
  });

  describe("Standard security headers in middleware", () => {
    it("should set HSTS header with preload", () => {
      expect(middlewareSource).toContain("Strict-Transport-Security");
      expect(middlewareSource).toContain("max-age=31536000");
      expect(middlewareSource).toContain("includeSubDomains");
      expect(middlewareSource).toContain("preload");
    });

    it("should set Referrer-Policy", () => {
      expect(middlewareSource).toContain("Referrer-Policy");
      expect(middlewareSource).toContain("strict-origin-when-cross-origin");
    });

    it("should set Permissions-Policy", () => {
      expect(middlewareSource).toContain("Permissions-Policy");
      expect(middlewareSource).toContain("camera=()");
      expect(middlewareSource).toContain("microphone=()");
      expect(middlewareSource).toContain("geolocation=()");
    });

    it("should set X-XSS-Protection", () => {
      expect(middlewareSource).toContain("X-XSS-Protection");
      expect(middlewareSource).toContain("1; mode=block");
    });
  });

  describe("AC3: CSP report endpoint exists", () => {
    it("should have csp-report route file", () => {
      const cspReportPath = path.join(
        __dirname,
        "..",
        "app",
        "api",
        "csp-report",
        "route.ts"
      );
      expect(fs.existsSync(cspReportPath)).toBe(true);
    });

    it("should export a POST handler", () => {
      const cspReportPath = path.join(
        __dirname,
        "..",
        "app",
        "api",
        "csp-report",
        "route.ts"
      );
      const source = fs.readFileSync(cspReportPath, "utf-8");
      expect(source).toContain("export async function POST");
    });
  });
});

/**
 * API proxy: GET /api/pseo/intel-feed -> backend GET /v1/pseo/intel-feed
 * Issue #1519 (NETINT-014): Embedded intelligence feed widget for SEO pages.
 *
 * Public endpoint (no auth). Cache: 1h revalidate (ISR-safe).
 * Falls back to static/generic data when backend is unavailable.
 */
import { NextRequest, NextResponse } from "next/server";

export interface IntelFeedSignal {
  label: string;
  value: string;
  trend?: "up" | "down" | "stable" | null;
}

export interface IntelFeedResponse {
  sector: string;
  signals: IntelFeedSignal[];
  generated_at: string;
}

/** Static fallback data for a sector — used when backend is offline */
function staticFallback(sector: string): IntelFeedResponse {
  const sectorName = sector.charAt(0).toUpperCase() + sector.slice(1);
  return {
    sector: sectorName,
    signals: [
      {
        label: "Acompanhe as oportunidades",
        value: `${sectorName}`,
        trend: null,
      },
      {
        label: "Mercado em análise",
        value: "Aguardando dados",
        trend: null,
      },
      {
        label: "Dados em consolidação",
        value: "Contratos deste mês",
        trend: null,
      },
    ],
    generated_at: new Date().toISOString(),
  };
}

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const sector = searchParams.get("sector");
  const uf = searchParams.get("uf");

  if (!sector) {
    return NextResponse.json({ error: "sector is required" }, { status: 400 });
  }

  const BACKEND_URL =
    process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL;

  if (!BACKEND_URL) {
    // No backend configured — serve static fallback
    const data = staticFallback(sector);
    return NextResponse.json(data, {
      headers: {
        "Cache-Control":
          "public, s-maxage=3600, stale-while-revalidate=7200",
      },
    });
  }

  try {
    const params = new URLSearchParams({ sector });
    if (uf) params.set("uf", uf);

    const resp = await fetch(
      `${BACKEND_URL}/v1/pseo/intel-feed?${params.toString()}`,
      {
        headers: { "Content-Type": "application/json" },
        next: { revalidate: 3600 },
        signal: AbortSignal.timeout(10000),
      },
    );

    if (!resp.ok) {
      // Backend error — serve static fallback
      const data = staticFallback(sector);
      return NextResponse.json(data, {
        headers: {
          "Cache-Control":
            "public, s-maxage=3600, stale-while-revalidate=7200",
        },
      });
    }

    const data: IntelFeedResponse = await resp.json();
    return NextResponse.json(data, {
      headers: {
        "Cache-Control":
          "public, s-maxage=3600, stale-while-revalidate=7200",
      },
    });
  } catch {
    // Network error — serve static fallback
    const data = staticFallback(sector);
    return NextResponse.json(data, {
      headers: {
        "Cache-Control":
          "public, s-maxage=3600, stale-while-revalidate=7200",
      },
    });
  }
}

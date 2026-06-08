/**
 * Sector stats proxy — public endpoint.
 * CONV-003-4: used by PartialReportPreview to fetch real opportunities per sector.
 * Proxies to GET /v1/sectors/{slug}/stats (public, no auth required).
 */
import { NextRequest, NextResponse } from "next/server";

const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL;

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ slug: string }> },
) {
  try {
    const { slug } = await params;
    const resp = await fetch(`${BACKEND_URL}/v1/sectors/${slug}/stats`, {
      headers: { "Content-Type": "application/json" },
      next: { revalidate: 21600 }, // 6h ISR
      signal: AbortSignal.timeout(10000),
    });

    if (!resp.ok) {
      if (resp.status === 404) {
        return NextResponse.json(
          { message: "Setor não encontrado" },
          { status: 404 },
        );
      }
      return NextResponse.json(
        { message: await resp.text() },
        { status: resp.status },
      );
    }

    const data = await resp.json();
    return NextResponse.json(data, {
      headers: {
        "Cache-Control": "public, s-maxage=21600, stale-while-revalidate=43200",
      },
    });
  } catch {
    return NextResponse.json(
      { message: "Erro de conexão ao buscar dados do setor" },
      { status: 502 },
    );
  }
}

import { NextRequest, NextResponse } from "next/server";

/**
 * API proxy: GET /api/subcontract/regional-dependency?setor={id}
 * Proxies to BACKEND_URL/v1/subcontract/regional-dependency?setor={id}
 *
 * SUBINTEL-012 (#1681): Regional Dependency Index
 */
export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const setor = searchParams.get("setor");

  if (!setor) {
    return NextResponse.json({ error: "setor query parameter is required" }, { status: 400 });
  }

  const authHeader = request.headers.get("authorization");
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    console.error("BACKEND_URL environment variable is not configured");
    return NextResponse.json({ error: "Servidor nao configurado" }, { status: 503 });
  }

  const backendParams = new URLSearchParams({ setor });

  const fullUrl = `${backendUrl}/v1/subcontract/regional-dependency?${backendParams}`;
  const headers: Record<string, string> = {};
  if (authHeader) {
    headers["Authorization"] = authHeader;
  }

  const correlationId = request.headers.get("X-Correlation-ID");
  if (correlationId) {
    headers["X-Correlation-ID"] = correlationId;
  }

  try {
    const res = await fetch(fullUrl, { headers });

    if (!res.ok) {
      const body = await res.text();
      try {
        const parsed = JSON.parse(body);
        return NextResponse.json(
          { error: parsed.detail || parsed.message || "Erro do servidor" },
          { status: res.status }
        );
      } catch {
        return NextResponse.json(
          { error: "Erro do servidor" },
          { status: res.status }
        );
      }
    }

    const data = await res.json().catch(() => null);
    if (!data) {
      return NextResponse.json(
        { error: "Resposta inesperada do servidor" },
        { status: 502 }
      );
    }
    return NextResponse.json(data);
  } catch (error) {
    console.error("[subcontract/regional-dependency] Network error:", error instanceof Error ? error.message : error);
    return NextResponse.json(
      { error: "Erro de conexao com o servidor" },
      { status: 502 }
    );
  }
}

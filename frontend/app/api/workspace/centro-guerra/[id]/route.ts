import { NextRequest, NextResponse } from "next/server";
import { sanitizeProxyError, sanitizeNetworkError } from "../../../../../lib/proxy-error-handler";

const BACKEND_URL = process.env.BACKEND_URL;

export async function GET(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  if (!BACKEND_URL) {
    console.error("BACKEND_URL environment variable is not configured");
    return NextResponse.json(
      { message: "Servico temporariamente indisponivel" },
      { status: 503 },
    );
  }

  const { id } = await params;

  if (!id) {
    return NextResponse.json({ message: "ID do edital nao informado." }, { status: 400 });
  }

  const url = `${BACKEND_URL}/v1/workspace/centro-guerra/${encodeURIComponent(id)}`;

  // Forward auth header from client session
  const authHeader = _request.headers.get("authorization");

  try {
    const headers: Record<string, string> = {};
    if (authHeader) {
      headers["Authorization"] = authHeader;
    }

    const response = await fetch(url, {
      headers,
      signal: AbortSignal.timeout(15000),
    });

    const body = await response.text();
    const sanitized = sanitizeProxyError(response.status, body, response.headers.get("content-type"));
    if (sanitized) return sanitized;

    try {
      const data = JSON.parse(body);
      return NextResponse.json(data, { status: response.status });
    } catch {
      return NextResponse.json(
        { message: "Resposta inesperada do servidor." },
        { status: 502 },
      );
    }
  } catch (error) {
    console.error("[workspace/centro-guerra] Network error:", error instanceof Error ? error.message : error);
    return sanitizeNetworkError(error);
  }
}

import { NextRequest, NextResponse } from "next/server";
import { sanitizeProxyError, sanitizeNetworkError } from "../../../../lib/proxy-error-handler";

const BACKEND_URL = process.env.BACKEND_URL;

export async function GET(request: NextRequest) {
  if (!BACKEND_URL) {
    console.error("BACKEND_URL environment variable is not configured");
    return NextResponse.json({ items: [], total: 0, message: "Servico temporariamente indisponivel" }, { status: 503 });
  }

  const authHeader = request.headers.get("authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) {
    return NextResponse.json({ items: [], total: 0, message: "Autenticacao necessaria." }, { status: 401 });
  }

  const url = `${BACKEND_URL}/v1/workspace/editais-hoje`;

  try {
    const response = await fetch(url, {
      headers: { Authorization: authHeader },
      signal: AbortSignal.timeout(10000),
    });

    const body = await response.text();
    const sanitized = sanitizeProxyError(response.status, body, response.headers.get("content-type"));
    if (sanitized) return sanitized;

    try {
      const data = JSON.parse(body);
      return NextResponse.json(data, { status: response.status });
    } catch {
      return NextResponse.json({ items: [], total: 0 }, { status: response.status });
    }
  } catch (error) {
    console.error("[workspace/editais-hoje] Network error:", error instanceof Error ? error.message : error);
    return sanitizeNetworkError(error);
  }
}

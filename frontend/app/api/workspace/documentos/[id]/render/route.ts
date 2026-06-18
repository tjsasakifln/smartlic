import { NextRequest, NextResponse } from "next/server";
import { sanitizeProxyError, sanitizeNetworkError } from "../../../../../../lib/proxy-error-handler";

const getBackendUrl = () => process.env.BACKEND_URL;

function getAuthHeader(request: NextRequest): string | null {
  const authHeader = request.headers.get("authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) return null;
  return authHeader;
}

/**
 * POST /api/workspace/documentos/{id}/render -> POST BACKEND_URL/v1/workspace/documentos/{id}/render
 */
export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const backendUrl = getBackendUrl();
  if (!backendUrl) {
    return NextResponse.json({ message: "Servico temporariamente indisponivel" }, { status: 503 });
  }

  const auth = getAuthHeader(request);
  if (!auth) {
    return NextResponse.json({ message: "Autenticacao necessaria." }, { status: 401 });
  }

  const { id } = await params;
  if (!id) {
    return NextResponse.json({ message: "ID do documento obrigatorio" }, { status: 400 });
  }

  const correlationId = request.headers.get("X-Correlation-ID");
  const headers: Record<string, string> = {
    Authorization: auth,
    "Content-Type": "application/json",
  };
  if (correlationId) {
    headers["X-Correlation-ID"] = correlationId;
  }

  try {
    const body = await request.json();
    const response = await fetch(`${backendUrl}/v1/workspace/documentos/${id}/render`, {
      method: "POST",
      headers,
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const responseBody = await response.text();
      const sanitized = sanitizeProxyError(response.status, responseBody, response.headers.get("content-type"));
      if (sanitized) return sanitized;

      try {
        const data = JSON.parse(responseBody);
        return NextResponse.json({ message: data.detail || data.message || "Erro ao renderizar documento" }, { status: response.status });
      } catch {
        return NextResponse.json({ message: "Erro temporario de comunicacao" }, { status: response.status });
      }
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("[workspace-documentos] POST render error:", error instanceof Error ? error.message : error);
    return sanitizeNetworkError(error);
  }
}

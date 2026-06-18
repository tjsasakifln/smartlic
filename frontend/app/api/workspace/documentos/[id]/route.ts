import { NextRequest, NextResponse } from "next/server";
import { sanitizeProxyError, sanitizeNetworkError } from "../../../../../lib/proxy-error-handler";

const getBackendUrl = () => process.env.BACKEND_URL;

function getAuthHeader(request: NextRequest): string | null {
  const authHeader = request.headers.get("authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) return null;
  return authHeader;
}

/**
 * GET /api/workspace/documentos/{id} -> GET BACKEND_URL/v1/workspace/documentos/{id}
 */
export async function GET(
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
  const headers: Record<string, string> = { Authorization: auth };
  if (correlationId) {
    headers["X-Correlation-ID"] = correlationId;
  }

  try {
    const response = await fetch(`${backendUrl}/v1/workspace/documentos/${id}`, { headers });

    if (!response.ok) {
      const body = await response.text();
      const sanitized = sanitizeProxyError(response.status, body, response.headers.get("content-type"));
      if (sanitized) return sanitized;

      try {
        const data = JSON.parse(body);
        return NextResponse.json({ message: data.detail || data.message || "Erro ao buscar documento" }, { status: response.status });
      } catch {
        return NextResponse.json({ message: "Erro temporario de comunicacao" }, { status: response.status });
      }
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("[workspace-documentos] GET error:", error instanceof Error ? error.message : error);
    return sanitizeNetworkError(error);
  }
}

/**
 * PATCH /api/workspace/documentos/{id} -> PATCH BACKEND_URL/v1/workspace/documentos/{id}
 */
export async function PATCH(
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
    const response = await fetch(`${backendUrl}/v1/workspace/documentos/${id}`, {
      method: "PATCH",
      headers,
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const responseBody = await response.text();
      const sanitized = sanitizeProxyError(response.status, responseBody, response.headers.get("content-type"));
      if (sanitized) return sanitized;

      try {
        const data = JSON.parse(responseBody);
        return NextResponse.json({ message: data.detail || data.message || "Erro ao atualizar documento" }, { status: response.status });
      } catch {
        return NextResponse.json({ message: "Erro temporario de comunicacao" }, { status: response.status });
      }
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("[workspace-documentos] PATCH error:", error instanceof Error ? error.message : error);
    return sanitizeNetworkError(error);
  }
}

/**
 * DELETE /api/workspace/documentos/{id} -> DELETE BACKEND_URL/v1/workspace/documentos/{id}
 */
export async function DELETE(
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
  const headers: Record<string, string> = { Authorization: auth };
  if (correlationId) {
    headers["X-Correlation-ID"] = correlationId;
  }

  try {
    const response = await fetch(`${backendUrl}/v1/workspace/documentos/${id}`, {
      method: "DELETE",
      headers,
    });

    if (!response.ok) {
      const responseBody = await response.text();
      const sanitized = sanitizeProxyError(response.status, responseBody, response.headers.get("content-type"));
      if (sanitized) return sanitized;

      try {
        const data = JSON.parse(responseBody);
        return NextResponse.json({ message: data.detail || data.message || "Erro ao excluir documento" }, { status: response.status });
      } catch {
        return NextResponse.json({ message: "Erro temporario de comunicacao" }, { status: response.status });
      }
    }

    if (response.status === 204) {
      return new NextResponse(null, { status: 204 });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("[workspace-documentos] DELETE error:", error instanceof Error ? error.message : error);
    return sanitizeNetworkError(error);
  }
}

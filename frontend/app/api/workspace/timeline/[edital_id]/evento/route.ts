import { NextRequest, NextResponse } from "next/server";
import { sanitizeProxyError, sanitizeNetworkError } from "../../../../../../lib/proxy-error-handler";

const BACKEND_URL = process.env.BACKEND_URL;

function getAuthHeader(request: NextRequest): string | null {
  const authHeader = request.headers.get("authorization");
  if (!authHeader || !authHeader.startsWith("Bearer ")) return null;
  return authHeader;
}

async function safeProxyResponse(
  response: Response,
  fallbackMessage: string,
): Promise<NextResponse> {
  const body = await response.text();
  const sanitized = sanitizeProxyError(
    response.status,
    body,
    response.headers.get("content-type"),
  );
  if (sanitized) return sanitized;

  try {
    const data = JSON.parse(body);
    return NextResponse.json(data, { status: response.status });
  } catch {
    return NextResponse.json(
      { message: fallbackMessage },
      { status: response.status },
    );
  }
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ edital_id: string }> },
) {
  if (!BACKEND_URL) {
    console.error("BACKEND_URL environment variable is not configured");
    return NextResponse.json({ message: "Serviço temporariamente indisponível" }, { status: 503 });
  }

  const auth = getAuthHeader(request);
  if (!auth) {
    return NextResponse.json({ message: "Autenticação necessária." }, { status: 401 });
  }

  const { edital_id } = await params;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Authorization: auth,
  };

  const correlationId = request.headers.get("X-Correlation-ID");
  if (correlationId) {
    headers["X-Correlation-ID"] = correlationId;
  }

  try {
    const body = await request.json();
    const response = await fetch(
      `${BACKEND_URL}/v1/workspace/timeline/${edital_id}/evento`,
      {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      },
    );
    return safeProxyResponse(response, "Erro ao criar evento.");
  } catch (error) {
    console.error("[workspace/timeline] Network error:", error instanceof Error ? error.message : error);
    return sanitizeNetworkError(error);
  }
}

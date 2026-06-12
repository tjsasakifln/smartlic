import { NextRequest, NextResponse } from "next/server";
import { getRefreshedToken } from "../../../../../../lib/serverAuth";
import { sanitizeProxyError } from "../../../../../../lib/proxy-error-handler";

/**
 * SUBINTEL-011 (#1674): Proxy for partnership score endpoint.
 * GET /api/v1/subcontract/partnership-score/{cnpj}
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ cnpj: string }> }
) {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    return NextResponse.json(
      { message: "Servidor nao configurado" },
      { status: 503 }
    );
  }

  const { cnpj } = await params;
  const refreshedToken = await getRefreshedToken();
  const authHeader = refreshedToken
    ? `Bearer ${refreshedToken}`
    : request.headers.get("authorization");

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (authHeader) {
    headers["Authorization"] = authHeader;
  }

  try {
    const response = await fetch(
      `${backendUrl}/v1/subcontract/partnership-score/${cnpj}`,
      { headers }
    );

    if (!response.ok) {
      const body = await response.text().catch(() => "");
      return NextResponse.json(
        { message: sanitizeProxyError(body) || "Erro ao buscar score" },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Erro de conexao";
    return NextResponse.json(
      { message: sanitizeProxyError(message) },
      { status: 502 }
    );
  }
}

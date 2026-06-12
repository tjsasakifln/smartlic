/**
 * Generic API proxy for /v1/* backend routes.
 * Forwards requests to the backend API and returns the response.
 */

import { NextRequest, NextResponse } from "next/server";
import { sanitizeNetworkError } from "../../../../lib/proxy-error-handler";

function getBackendUrl(): string {
  const backendUrl = process.env.BACKEND_URL;
  if (!backendUrl) {
    throw new Error("BACKEND_URL environment variable is not configured");
  }
  return backendUrl;
}

async function handleV1Request(
  request: NextRequest,
  params: Promise<{ path: string[] }>,
  method: string,
): Promise<NextResponse> {
  try {
    const { path } = await params;
    const backendUrl = getBackendUrl();
    const pathStr = path.join("/");
    const searchParams = request.nextUrl.searchParams.toString();
    const url = `${backendUrl}/v1/${pathStr}${searchParams ? `?${searchParams}` : ""}`;

    const headers: Record<string, string> = {
      "Content-Type": request.headers.get("content-type") || "application/json",
    };

    // Forward authorization header
    const auth = request.headers.get("authorization");
    if (auth) {
      headers["Authorization"] = auth;
    }

    // Forward cookie header
    const cookie = request.headers.get("cookie");
    if (cookie) {
      headers["Cookie"] = cookie;
    }

    const body = method === "GET" || method === "HEAD" ? undefined : await request.text();

    const response = await fetch(url, {
      method,
      headers,
      body: body || undefined,
    });

    const responseBody = await response.text();

    // Try to parse as JSON, fall back to text
    let parsed: unknown;
    try {
      parsed = JSON.parse(responseBody);
    } catch {
      parsed = responseBody;
    }

    return NextResponse.json(parsed, {
      status: response.status,
      headers: {
        "Content-Type": "application/json",
      },
    });
  } catch (error) {
    console.error(`V1 proxy error (${method}):`, error);
    return sanitizeNetworkError(error);
  }
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return handleV1Request(request, params, "GET");
}

export async function POST(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return handleV1Request(request, params, "POST");
}

export async function PUT(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return handleV1Request(request, params, "PUT");
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return handleV1Request(request, params, "PATCH");
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  return handleV1Request(request, params, "DELETE");
}

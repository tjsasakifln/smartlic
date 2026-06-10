/**
 * GAP-005: SSE polling fallback state endpoint.
 *
 * GET /api/v1/buscar/{id}/state -> backend GET /v1/search/{id}/status
 *
 * Used by useSearchSSE when heartbeat is lost — poll this endpoint
 * every 5s to get the current search state without SSE.
 */

import type { NextRequest } from "next/server";
import { createProxyRoute } from "../../../../../../lib/create-proxy-route";

export const { GET } = createProxyRoute({
  backendPath: (request: NextRequest) => {
    const url = new URL(request.url);
    const id = url.pathname.split("/").filter(Boolean).pop() || "";
    return `/v1/search/${encodeURIComponent(id)}/status`;
  },
  methods: ["GET"],
  requireAuth: false,
  forwardQuery: false,
  errorMessage: "Erro temporário de comunicação",
});

/**
 * B2GOPS-011 (#2021): Workspace alertas mark-as-read API proxy.
 * PATCH /api/workspace/alertas/[id]/read -> PATCH BACKEND_URL/v1/workspace/alertas/{id}/read
 */
import { NextRequest } from "next/server";
import { createProxyRoute } from "../../../../../../lib/create-proxy-route";

export const { PATCH } = createProxyRoute({
  backendPath: (request: NextRequest) => {
    const url = new URL(request.url);
    const segments = url.pathname.split("/");
    const alertId = segments[segments.length - 2]; // .../alertas/{id}/read
    return `/v1/workspace/alertas/${alertId}/read`;
  },
  methods: ["PATCH"],
  requireAuth: true,
  allowRefresh: true,
  errorMessage: "Erro ao marcar alerta como lido",
  forwardQuery: false,
});

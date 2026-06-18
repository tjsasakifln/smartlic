/**
 * B2GOPS-011 (#2021): Workspace alertas API proxy.
 * GET  /api/workspace/alertas               -> GET    BACKEND_URL/v1/workspace/alertas
 * PATCH /api/workspace/alertas/{id}/read     -> PATCH  BACKEND_URL/v1/workspace/alertas/{id}/read
 *
 * Also proxies unread-count sub-route.
 */
import { NextRequest, NextResponse } from "next/server";
import { createProxyRoute } from "../../../../lib/create-proxy-route";

export const { GET } = createProxyRoute({
  backendPath: "/v1/workspace/alertas",
  methods: ["GET"],
  requireAuth: true,
  allowRefresh: true,
  errorMessage: "Erro ao listar alertas",
});

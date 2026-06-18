/**
 * B2GOPS-011 (#2021): Unread count proxy.
 * GET /api/workspace/alertas/unread-count -> GET BACKEND_URL/v1/workspace/alertas/unread-count
 */
import { createProxyRoute } from "../../../../../lib/create-proxy-route";

export const { GET } = createProxyRoute({
  backendPath: "/v1/workspace/alertas/unread-count",
  methods: ["GET"],
  requireAuth: true,
  allowRefresh: true,
  errorMessage: "Erro ao obter contagem de alertas",
  forwardQuery: false,
});

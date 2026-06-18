/**
 * B2GOPS-011 (#2021): Workspace watchlist API proxy.
 * GET  /api/workspace/watchlist   -> GET    BACKEND_URL/v1/workspace/watchlist
 * POST /api/workspace/watchlist   -> POST   BACKEND_URL/v1/workspace/watchlist
 */
import { createProxyRoute } from "../../../../lib/create-proxy-route";

export const { GET, POST } = createProxyRoute({
  backendPath: "/v1/workspace/watchlist",
  methods: ["GET", "POST"],
  requireAuth: true,
  allowRefresh: true,
  errorMessage: "Erro ao processar watchlist",
});

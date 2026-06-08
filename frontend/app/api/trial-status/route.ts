/**
 * Trial status proxy — requires auth.
 */
import { createProxyRoute } from "../../../lib/create-proxy-route";

export const { GET } = createProxyRoute({
  backendPath: "/v1/trial-status",
  requireAuth: true,
    allowRefresh: true,
  errorMessage: "Erro do servidor",
});

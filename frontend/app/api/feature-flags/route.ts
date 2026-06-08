/**
 * DEBT-205 / DEBT-SYS-009: Feature flags proxy.
 * Authenticated endpoint — returns active feature flags for frontend consumption.
 */
import { createProxyRoute } from "../../../lib/create-proxy-route";

export const { GET } = createProxyRoute({
  backendPath: "/v1/feature-flags",
  requireAuth: true,
    allowRefresh: true,
  fetchCache: { revalidate: 300 }, // 5 min cache
  errorMessage: "Erro ao buscar feature flags.",
});

/**
 * Profile context proxy — requires auth, GET + PUT.
 */
import { createProxyRoute } from "../../../lib/create-proxy-route";

export const { GET, PUT } = createProxyRoute({
  backendPath: "/v1/profile/context",
  methods: ["GET", "PUT"],
  requireAuth: true,
    allowRefresh: true,
  errorMessage: "Erro ao obter contexto",
});

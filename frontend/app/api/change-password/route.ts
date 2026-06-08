/**
 * Change password proxy — requires auth, POST only.
 */
import { createProxyRoute } from "../../../lib/create-proxy-route";

export const { POST } = createProxyRoute({
  backendPath: "/v1/change-password",
  methods: ["POST"],
  requireAuth: true,
    allowRefresh: true,
  errorMessage: "Erro ao alterar senha",
});

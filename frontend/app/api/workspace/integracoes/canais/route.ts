import { createProxyRoute } from "../../../../../lib/create-proxy-route";

export const { GET, POST } = createProxyRoute({
  backendPath: "/v1/workspace/integracoes/canais",
  methods: ["GET", "POST"],
  allowRefresh: true,
  errorMessage: "Erro ao acessar canais de integracao",
  logPrefix: "workspace-integracoes",
});

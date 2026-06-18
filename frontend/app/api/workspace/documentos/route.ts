import { createProxyRoute } from "../../../../lib/create-proxy-route";

export const { GET, POST } = createProxyRoute({
  backendPath: "/v1/workspace/documentos",
  methods: ["GET", "POST"],
  requireAuth: true,
  allowRefresh: true,
  errorMessage: "Erro ao processar documentos",
});

import { createProxyRoute } from "../../../../lib/create-proxy-route";

export const { GET } = createProxyRoute({
  backendPath: "/v1/workspace/templates",
  methods: ["GET"],
  requireAuth: true,
  allowRefresh: true,
  errorMessage: "Erro ao listar templates",
});

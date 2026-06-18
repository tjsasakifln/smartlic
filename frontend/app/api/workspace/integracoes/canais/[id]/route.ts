import { createProxyRoute } from "../../../../../../lib/create-proxy-route";

export const { DELETE } = createProxyRoute({
  backendPath: (request) => {
    const segments = request.nextUrl.pathname.split("/");
    const id = segments[segments.length - 1];
    return `/v1/workspace/integracoes/canais/${id}`;
  },
  methods: ["DELETE"],
  allowRefresh: true,
  errorMessage: "Erro ao remover canal de integracao",
  logPrefix: "workspace-integracoes-delete",
});

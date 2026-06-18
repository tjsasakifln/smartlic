import { createProxyRoute } from "../../../../../../lib/create-proxy-route";

export const { POST } = createProxyRoute({
  backendPath: (request) => {
    const segments = request.nextUrl.pathname.split("/");
    const id = segments[segments.length - 1];
    return `/v1/workspace/integracoes/test/${id}`;
  },
  methods: ["POST"],
  allowRefresh: true,
  errorMessage: "Erro ao enviar notificacao de teste",
  forwardQuery: false,
  logPrefix: "workspace-integracoes-test",
});

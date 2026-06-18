/**
 * B2GOPS-011 (#2021): Workspace watchlist item delete proxy.
 * DELETE /api/workspace/watchlist/[id] -> DELETE BACKEND_URL/v1/workspace/watchlist/{id}
 */
import { NextRequest } from "next/server";
import { createProxyRoute } from "../../../../lib/create-proxy-route";

export const { DELETE } = createProxyRoute({
  backendPath: (request: NextRequest) => {
    const url = new URL(request.url);
    const segments = url.pathname.split("/");
    const id = segments[segments.length - 1];
    return `/v1/workspace/watchlist/${id}`;
  },
  methods: ["DELETE"],
  requireAuth: true,
  allowRefresh: true,
  errorMessage: "Erro ao remover da watchlist",
  forwardQuery: false,
});

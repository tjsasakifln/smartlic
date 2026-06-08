/**
 * GTM-RESILIENCE-D05: Feedback API proxy.
 *
 * POST /api/feedback → POST BACKEND_URL/v1/feedback
 * DELETE /api/feedback?id=xxx → DELETE BACKEND_URL/v1/feedback/{id}
 *
 * Note: DELETE uses dynamic path via query param, so we use the function form.
 */

import type { NextRequest } from "next/server";
import { createProxyRoute } from "../../../lib/create-proxy-route";

export const { POST } = createProxyRoute({
  backendPath: "/v1/feedback",
  methods: ["POST"],
  requireAuth: true,
    allowRefresh: true,
  errorMessage: "Erro ao enviar feedback",
});

// DELETE needs dynamic path (feedback/{id}), so it uses the function form
const deleteHandlers = createProxyRoute({
  backendPath: (request: NextRequest) => {
    const feedbackId = new URL(request.url).searchParams.get("id");
    return `/v1/feedback/${feedbackId || ""}`;
  },
  methods: ["DELETE"],
  requireAuth: true,
    allowRefresh: true,
  forwardQuery: false,
  errorMessage: "Erro ao remover feedback",
});

export const DELETE = deleteHandlers.DELETE;

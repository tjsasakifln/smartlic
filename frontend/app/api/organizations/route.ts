/**
 * Organizations proxy — GET fetches user's org, POST creates new org.
 * Note: GET maps to /v1/organizations/me, POST maps to /v1/organizations.
 */

import type { NextRequest } from "next/server";
import { createProxyRoute } from "../../../lib/create-proxy-route";

// GET /api/organizations → GET /v1/organizations/me
const getHandlers = createProxyRoute({
  backendPath: "/v1/organizations/me",
  methods: ["GET"],
  requireAuth: true,
    allowRefresh: true,
  errorMessage: "Erro ao obter organizacao",
});

// POST /api/organizations → POST /v1/organizations
const postHandlers = createProxyRoute({
  backendPath: "/v1/organizations",
  methods: ["POST"],
  requireAuth: true,
    allowRefresh: true,
  errorMessage: "Erro ao criar organizacao",
});

export const GET = getHandlers.GET;
export const POST = postHandlers.POST;

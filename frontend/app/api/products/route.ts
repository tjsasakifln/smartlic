/**
 * Products listing proxy — GET /v1/products
 * Public (no auth required). Returns list of active digital products.
 * CONV-005b-3: Used by DigitalProductPreview to fetch product data by SKU.
 */
import { createProxyRoute } from "../../../lib/create-proxy-route";

export const { GET } = createProxyRoute({
  backendPath: "/v1/products",
  methods: ["GET"],
  requireAuth: false,
  fetchCache: { revalidate: 300 },
  errorMessage: "Erro ao carregar produtos.",
});

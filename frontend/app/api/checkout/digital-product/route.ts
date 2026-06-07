/**
 * Digital product checkout proxy — POST /api/checkout/one-time
 * Authenticated. Returns { checkout_url } from backend.
 * Frontend redirects user to checkout_url (Stripe Checkout).
 * CONV-005b-3: Used by CheckoutModal to initiate digital product purchase.
 */
import { createProxyRoute } from "../../../../lib/create-proxy-route";

export const { POST } = createProxyRoute({
  backendPath: "/api/checkout/one-time",
  methods: ["POST"],
  requireAuth: true,
  errorMessage: "Não foi possível iniciar o checkout do produto digital.",
});

import { Suspense } from "react";
import { Metadata } from "next";
import ObrigadoClient from "./ObrigadoClient";

/**
 * Thank-you page after a successful one-time digital product checkout.
 *
 * Server Component shell: exports metadata and wraps the dynamic content
 * in Suspense (required because ObrigadoClient reads useSearchParams).
 * The actual session status polling and UI are handled by ObrigadoClient ("use client").
 */
export const metadata: Metadata = {
  title: "Pagamento Confirmado",
  description: "Seu pagamento foi confirmado com sucesso.",
  robots: { index: false, follow: false },
};

export default function ObrigadoPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-[var(--canvas)] flex items-center justify-center">
        <div className="animate-pulse text-[var(--ink-muted)]">Carregando...</div>
      </div>
    }>
      <ObrigadoClient />
    </Suspense>
  );
}

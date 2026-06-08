"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { CheckCircle, Loader2, AlertCircle, PartyPopper } from "lucide-react";
import { toast } from "sonner";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type FetchState = "loading" | "success" | "not_found" | "error";

interface SessionStatus {
  status: string; // "pending" | "generating" | "ready" | "failed" | "completed"
  product_name?: string | null;
  sku?: string | null;
  pdf_url?: string | null;
  created_at?: string | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function trackEvent(name: string, props?: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  const mp = (
    window as unknown as { mixpanel?: { track: (e: string, p?: Record<string, unknown>) => void } }
  ).mixpanel;
  if (!mp) return;
  try {
    mp.track(name, props ?? {});
  } catch {
    // best-effort
  }
}

function statusLabel(status: string): string {
  switch (status) {
    case "pending":
    case "generating":
      return "Seu relatório está sendo gerado.";
    case "ready":
      return "Seu relatório está pronto para download!";
    case "completed":
      return "Pagamento confirmado! Seu produto está disponível.";
    case "failed":
      return "Ocorreu um erro no processamento. Entre em contato com o suporte.";
    default:
      return "Pagamento confirmado!";
  }
}

function statusIcon(status: string): React.ReactNode {
  switch (status) {
    case "pending":
    case "generating":
      return <Loader2 className="w-8 h-8 text-[var(--brand-blue)] animate-spin" />;
    case "ready":
    case "completed":
      return <CheckCircle className="w-8 h-8 text-[var(--success)]" />;
    case "failed":
      return <AlertCircle className="w-8 h-8 text-red-500" />;
    default:
      return <CheckCircle className="w-8 h-8 text-[var(--success)]" />;
  }
}

function statusBgClass(status: string): string {
  switch (status) {
    case "pending":
    case "generating":
      return "bg-blue-50";
    case "ready":
    case "completed":
      return "bg-emerald-50";
    case "failed":
      return "bg-red-50";
    default:
      return "bg-emerald-50";
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ObrigadoClient() {
  const searchParams = useSearchParams();
  const [sessionStatus, setSessionStatus] = useState<SessionStatus | null>(null);
  const [fetchState, setFetchState] = useState<FetchState>("loading");
  const [statusMessage, setStatusMessage] = useState("");

  const sessionId = searchParams.get("session_id");

  // Track page view
  useEffect(() => {
    trackEvent("obrigado_page_viewed", { session_id: sessionId });
  }, [sessionId]);

  // Fetch session status
  useEffect(() => {
    if (!sessionId) {
      setFetchState("not_found");
      setStatusMessage("Nenhuma sessão de pagamento encontrada.");
      return;
    }

    let cancelled = false;

    const fetchStatus = async () => {
      try {
        const res = await fetch(`/api/checkout/session/${encodeURIComponent(sessionId)}`);

        if (!res.ok) {
          if (res.status === 404) {
            if (!cancelled) {
              setFetchState("not_found");
              setStatusMessage("Compra não encontrada. Pode levar alguns instantes para o pagamento ser processado.");
            }
            return;
          }
          throw new Error(`HTTP ${res.status}`);
        }

        const data: SessionStatus = await res.json();

        if (cancelled) return;

        setSessionStatus(data);
        setFetchState("success");
        setStatusMessage(statusLabel(data.status));

        // Track success
        trackEvent("obrigado_session_loaded", {
          session_id: sessionId,
          status: data.status,
          sku: data.sku,
        });

        // Show toast on success states
        if (data.status === "ready" || data.status === "completed") {
          toast.success("Pagamento confirmado com sucesso!", {
            duration: 5000,
            icon: <PartyPopper className="w-5 h-5" />,
          });
        }
      } catch (err) {
        if (!cancelled) {
          setFetchState("error");
          setStatusMessage(
            "Não foi possível verificar o status da compra. Tente novamente em instantes."
          );
        }
      }
    };

    fetchStatus();

    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const isProcessing =
    sessionStatus?.status === "pending" || sessionStatus?.status === "generating";
  const isReady =
    sessionStatus?.status === "ready" || sessionStatus?.status === "completed";
  const isFailed = sessionStatus?.status === "failed";

  return (
    <div className="min-h-screen bg-[var(--canvas)] flex items-center justify-center px-4">
      <div className="max-w-lg w-full text-center">
        <div className="bg-[var(--surface-0)] border border-[var(--border)] rounded-card p-8 shadow-lg">
          {/* Status Icon */}
          <div
            className={`w-16 h-16 mx-auto mb-6 rounded-full flex items-center justify-center ${statusBgClass(sessionStatus?.status || "completed")}`}
          >
            {fetchState === "loading" ? (
              <Loader2 className="w-8 h-8 text-[var(--brand-blue)] animate-spin" />
            ) : (
              statusIcon(sessionStatus?.status || "completed")
            )}
          </div>

          {/* Title */}
          {fetchState === "loading" ? (
            <>
              <h1 className="text-2xl font-display font-bold text-[var(--ink)] mb-2">
                Verificando pagamento...
              </h1>
              <p className="text-[var(--ink-secondary)] mb-4">
                Estamos confirmando sua compra. Isso leva apenas alguns segundos.
              </p>
              <div className="flex items-center justify-center gap-2 text-sm text-[var(--ink-muted)]">
                <Loader2 className="w-4 h-4 animate-spin" />
                Verificando...
              </div>
            </>
          ) : fetchState === "not_found" ? (
            <>
              <h1 className="text-2xl font-display font-bold text-[var(--ink)] mb-2">
                Pagamento em processamento
              </h1>
              <p className="text-[var(--ink-secondary)] mb-4">{statusMessage}</p>
              <div className="p-4 bg-[var(--surface-1)] rounded-input text-left mb-4">
                <p className="text-sm text-[var(--ink-secondary)]">
                  Se você pagou com boleto ou PIX, a confirmação pode levar alguns minutos.
                  Você receberá um email assim que a compra for confirmada.
                </p>
              </div>
            </>
          ) : fetchState === "error" ? (
            <>
              <h1 className="text-2xl font-display font-bold text-[var(--ink)] mb-2">
                Algo deu errado
              </h1>
              <p className="text-[var(--ink-secondary)] mb-4">{statusMessage}</p>
              <div className="p-4 bg-[var(--surface-1)] rounded-input text-left mb-4">
                <p className="text-sm text-[var(--ink-secondary)]">
                  Seu pagamento foi processado pelo Stripe. Se o problema persistir,
                  entre em contato pelo email{" "}
                  <a
                    href="mailto:tiago@confenge.com.br"
                    className="text-[var(--brand-blue)] underline"
                  >
                    tiago@confenge.com.br
                  </a>
                  .
                </p>
              </div>
            </>
          ) : isProcessing ? (
            <>
              <h1 className="text-2xl font-display font-bold text-[var(--ink)] mb-2">
                Pagamento confirmado!
              </h1>
              <p className="text-[var(--ink-secondary)] mb-2">{statusMessage}</p>
              <p className="text-sm text-[var(--ink-muted)] mb-4">
                Você receberá um email assim que o relatório estiver pronto.
              </p>
              {sessionStatus?.sku && (
                <div className="p-3 bg-[var(--surface-1)] rounded-input mb-4">
                  <p className="text-sm font-medium text-[var(--ink)]">
                    {sessionStatus.product_name || sessionStatus.sku}
                  </p>
                  <p className="text-xs text-[var(--ink-muted)] mt-1">
                    Em processamento...
                  </p>
                </div>
              )}
            </>
          ) : isReady ? (
            <>
              <h1 className="text-2xl font-display font-bold text-[var(--ink)] mb-2">
                Pagamento confirmado!
              </h1>
              <p className="text-[var(--ink-secondary)] mb-4">{statusMessage}</p>

              {sessionStatus?.sku && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 rounded-input mb-4">
                  <p className="text-sm font-medium text-emerald-800">
                    {sessionStatus.product_name || sessionStatus.sku}
                  </p>
                  {sessionStatus.pdf_url ? (
                    <a
                      href={sessionStatus.pdf_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-2 inline-block text-sm font-medium text-[var(--brand-blue)] underline hover:text-[var(--brand-blue-hover)]"
                    >
                      Baixar relatório
                    </a>
                  ) : (
                    <p className="text-xs text-emerald-600 mt-1">
                      Disponível para download
                    </p>
                  )}
                </div>
              )}

              {!sessionStatus?.sku && (
                <p className="text-lg text-[var(--ink-secondary)] mb-4">
                  Obrigado pela confiança!
                </p>
              )}
            </>
          ) : isFailed ? (
            <>
              <h1 className="text-2xl font-display font-bold text-[var(--ink)] mb-2">
                Erro no processamento
              </h1>
              <p className="text-[var(--ink-secondary)] mb-4">{statusMessage}</p>
              <div className="p-4 bg-[var(--surface-1)] rounded-input text-left mb-4">
                <p className="text-sm text-[var(--ink-secondary)]">
                  Seu pagamento foi processado, mas ocorreu um erro ao gerar o relatório.
                  Entre em contato pelo email{" "}
                  <a
                    href="mailto:tiago@confenge.com.br"
                    className="text-[var(--brand-blue)] underline"
                  >
                    tiago@confenge.com.br
                  </a>{" "}
                  para resolvermos o problema.
                </p>
              </div>
            </>
          ) : (
            <>
              <h1 className="text-2xl font-display font-bold text-[var(--ink)] mb-2">
                Pagamento confirmado!
              </h1>
              <p className="text-[var(--ink-secondary)] mb-4">
                Obrigado pela confiança!
              </p>
            </>
          )}

          {/* Action buttons */}
          <div className="space-y-3 mt-6">
            <Link
              href="/buscar"
              className="block w-full py-3 bg-[var(--brand-navy)] text-white rounded-button font-semibold hover:bg-[var(--brand-blue)] transition-colors"
            >
              Ir para busca
            </Link>
            <Link
              href="/conta"
              className="block w-full py-3 border border-[var(--border)] text-[var(--ink)] rounded-button font-semibold hover:bg-[var(--surface-1)] transition-colors"
            >
              Ver minhas compras
            </Link>
          </div>

          {/* Support footer */}
          <p className="mt-6 text-xs text-[var(--ink-muted)]">
            Dúvidas? Escreva para{" "}
            <a
              href="mailto:tiago@confenge.com.br"
              className="text-[var(--brand-blue)] underline"
            >
              tiago@confenge.com.br
            </a>
          </p>
        </div>
      </div>
    </div>
  );
}

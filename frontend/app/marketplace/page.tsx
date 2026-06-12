"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { AuthLoadingScreen } from "@/components/AuthLoadingScreen";
import { useAuth } from "@/app/components/AuthProvider";
import { PageHeader } from "@/components/PageHeader";
import { EmptyState } from "@/components/EmptyState";
import { ErrorStateWithRetry } from "@/components/ErrorStateWithRetry";
import { OpportunityCard } from "./components/OpportunityCard";
import { MarketplaceFilters } from "./components/MarketplaceFilters";
import { ExpressInterestForm } from "./components/ExpressInterestForm";

// --- Types ---

interface SubcontractOpportunity {
  id: string;
  contract_id: string | null;
  winner_cnpj: string;
  winner_name: string | null;
  sector: string | null;
  value: number | null;
  services_needed: string[];
  status: string;
  uf: string | null;
  municipio: string | null;
  orgao_nome: string | null;
  objeto: string | null;
  discovery_reason: string | null;
  created_at: string;
  interest_count: number;
}

interface PaginatedResponse {
  opportunities: SubcontractOpportunity[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// --- Constants ---
const PAGE_SIZE = 20;

// --- API helper ---

async function fetchOpportunities(
  params: { setor?: string; uf?: string; page?: number },
  signal?: AbortSignal
): Promise<PaginatedResponse> {
  const searchParams = new URLSearchParams();
  if (params.setor) searchParams.set("setor", params.setor);
  if (params.uf) searchParams.set("uf", params.uf);
  if (params.page) searchParams.set("page", String(params.page));
  searchParams.set("page_size", String(PAGE_SIZE));

  const res = await fetch(`/v1/marketplace/opportunities?${searchParams.toString()}`, {
    credentials: "include",
    signal,
  });
  if (!res.ok) {
    if (res.status === 404) {
      return { opportunities: [], total: 0, page: 1, page_size: PAGE_SIZE, total_pages: 0 };
    }
    throw new Error(`Erro ao carregar oportunidades (${res.status})`);
  }
  return res.json();
}

// --- Page Component ---

export default function MarketplacePage() {
  const { user, loading: authLoading } = useAuth();
  const [opportunities, setOpportunities] = useState<SubcontractOpportunity[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterSetor, setFilterSetor] = useState<string>("");
  const [filterUf, setFilterUf] = useState<string>("");
  const [interestOppId, setInterestOppId] = useState<string | null>(null);
  const [interestSubmitted, setInterestSubmitted] = useState<Set<string>>(new Set());

  const loadOpportunities = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchOpportunities(
        {
          setor: filterSetor || undefined,
          uf: filterUf || undefined,
          page,
        },
        signal
      );
      setOpportunities(data.opportunities);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") return;
      setError(err instanceof Error ? err.message : "Erro desconhecido");
    } finally {
      setLoading(false);
    }
  }, [filterSetor, filterUf, page]);

  useEffect(() => {
    const abortController = new AbortController();
    loadOpportunities(abortController.signal);
    return () => abortController.abort();
  }, [loadOpportunities]);

  const handleFilterChange = useCallback(
    (setor: string, uf: string) => {
      setFilterSetor(setor);
      setFilterUf(uf);
      setPage(1);
    },
    []
  );

  const handleInterest = useCallback((oppId: string) => {
    setInterestOppId(oppId);
  }, []);

  const handleInterestClose = useCallback(() => {
    setInterestOppId(null);
  }, []);

  const handleInterestSuccess = useCallback((oppId: string) => {
    setInterestSubmitted((prev) => new Set(prev).add(oppId));
    setInterestOppId(null);
    // Reload to update interest count
    loadOpportunities(new AbortController().signal);
  }, [loadOpportunities]);

  if (authLoading) return <AuthLoadingScreen />;
  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[var(--bg-primary)]">
        <div className="text-center max-w-md mx-auto p-8">
          <h1 className="text-2xl font-bold mb-4 text-[var(--text-primary)]">
            Marketplace de Subcontratação
          </h1>
          <p className="text-[var(--text-secondary)] mb-6">
            Faça login para acessar oportunidades de subcontratação em contratos públicos.
          </p>
          <Link href="/login">
            <Button variant="primary">Fazer Login</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--bg-primary)]">
      <div className="max-w-7xl mx-auto px-4 py-6">
        <PageHeader
          title="Marketplace de Subcontratação"
        />
        <p className="text-sm text-[var(--text-secondary)] mb-6">
          Oportunidades de subcontratação identificadas automaticamente em contratos públicos
        </p>

        {/* Filters */}
        <MarketplaceFilters
          setor={filterSetor}
          uf={filterUf}
          onFilterChange={handleFilterChange}
        />

        {/* Results info */}
        <div className="mb-4 text-sm text-[var(--text-secondary)]">
          {loading ? "Carregando..." : `${total} oportunidade${total !== 1 ? "s" : ""} encontrada${total !== 1 ? "s" : ""}`}
        </div>

        {/* Error state */}
        {error && (
          <ErrorStateWithRetry
            message={error}
            onRetry={() => loadOpportunities(new AbortController().signal)}
          />
        )}

        {/* Loading state */}
        {loading && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <div
                key={i}
                className="h-48 rounded-xl bg-[var(--surface-1)] animate-pulse"
                data-testid="marketplace-skeleton"
              />
            ))}
          </div>
        )}

        {/* Empty state */}
        {!loading && !error && opportunities.length === 0 && (
          <EmptyState
            icon={<Search className="w-8 h-8 text-[var(--ink-secondary)]" />}
            title="Nenhuma oportunidade encontrada"
            description="No momento não há oportunidades de subcontratação disponíveis com os filtros selecionados."
            ctaLabel="Ajustar filtros"
            ctaHref="#"
          />
        )}

        {/* Opportunity cards */}
        {!loading && !error && opportunities.length > 0 && (
          <>
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              {opportunities.map((opp) => (
                <OpportunityCard
                  key={opp.id}
                  opportunity={opp}
                  hasInterest={interestSubmitted.has(opp.id)}
                  onInterest={() => handleInterest(opp.id)}
                />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex justify-center gap-2 mt-8">
                <Button
                  variant="secondary"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  Anterior
                </Button>
                <span className="flex items-center px-4 text-sm text-[var(--text-secondary)]">
                  Página {page} de {totalPages}
                </span>
                <Button
                  variant="secondary"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Próxima
                </Button>
              </div>
            )}
          </>
        )}

        {/* Express interest modal */}
        {interestOppId && (
          <ExpressInterestForm
            opportunityId={interestOppId}
            onClose={handleInterestClose}
            onSuccess={() => handleInterestSuccess(interestOppId)}
          />
        )}
      </div>
    </div>
  );
}

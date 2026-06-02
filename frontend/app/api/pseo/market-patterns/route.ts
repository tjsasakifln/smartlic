/**
 * API proxy: GET /api/pseo/market-patterns → backend GET /v1/pseo/market-patterns
 * Issue #1288 (NETINT-011): Padrões de Mercado — aggregated market intelligence per setor.
 *
 * Stub implementation: returns mock data until backend RPC (NETINT-002/003/004) is available.
 * When backend endpoint is ready, uncomment the proxy logic and remove mock data.
 *
 * Public endpoint (no auth). Cache: 6h CDN + SWR.
 */
import { NextRequest, NextResponse } from "next/server";

export interface MarketPatternsResponse {
  setor: string;
  setor_nome: string;
  media_licitacoes_mes: number;
  valor_medio_contratos: number;
  top_orgaos: {
    nome: string;
    total_contratos: number;
    valor_total: number;
  }[];
  sazonalidade: {
    mes: string;
    total_publicacoes: number;
  }[];
  total_empresas_entrantes: number;
  tendencia_desconto: {
    desconto_medio_pct: number;
    variacao_anual_pct: number;
  };
  last_updated: string;
}

/** Sector display names for mock data */
const SECTOR_NAMES: Record<string, string> = {
  vestuario: "Vestuário e Uniformes",
  alimentos: "Alimentos e Merenda",
  informatica: "Hardware e Equipamentos de TI",
  mobiliario: "Mobiliário",
  papelaria: "Papelaria e Material de Escritório",
  engenharia: "Engenharia, Projetos e Obras",
  software: "Software e Sistemas",
  facilities: "Facilities e Manutenção",
  saude: "Saúde",
  vigilancia: "Vigilância e Segurança Patrimonial",
  transporte: "Transporte e Veículos",
  "manutencao-predial": "Manutenção e Conservação Predial",
  "engenharia-rodoviaria": "Engenharia Rodoviária e Infraestrutura Viária",
  "materiais-eletricos": "Materiais Elétricos e Instalações",
  "materiais-hidraulicos": "Materiais Hidráulicos e Saneamento",
};

/**
 * Generates realistic mock market-patterns data for a given sector.
 * Uses a deterministic hash from the setor name so values are consistent
 * per sector but differ between sectors.
 */
function generateMockData(setor: string): MarketPatternsResponse {
  const setorNome = SECTOR_NAMES[setor] ?? setor;
  // Deterministic seed from setor name for consistent per-sector values
  const hash = [...setor].reduce((acc: number, c: string) => acc + c.charCodeAt(0), 0);

  const baseMonthlyBids = 80 + (hash % 120);
  const baseAvgValue = 150_000 + (hash % 350) * 1_000;
  const descontoMedio = 8 + (hash % 25);
  const variacaoAnual = -15 + (hash % 30);

  const orgaos = [
    { nome: "Prefeitura Municipal", total_contratos: 25 + (hash % 30), valor_total: 1_200_000 + (hash % 800) * 1_000 },
    { nome: "Governo Estadual", total_contratos: 18 + (hash % 20), valor_total: 3_500_000 + (hash % 500) * 1_000 },
    { nome: "Ministério da Saúde", total_contratos: 10 + (hash % 15), valor_total: 800_000 + (hash % 400) * 1_000 },
    { nome: "Secretaria de Educação", total_contratos: 12 + (hash % 10), valor_total: 500_000 + (hash % 300) * 1_000 },
    { nome: "Departamento de Obras", total_contratos: 8 + (hash % 12), valor_total: 4_200_000 + (hash % 600) * 1_000 },
  ];

  const meses = [
    { mes: "Jan", total_publicacoes: 60 + (hash % 40) },
    { mes: "Fev", total_publicacoes: 55 + (hash % 35) },
    { mes: "Mar", total_publicacoes: 75 + (hash % 45) },
    { mes: "Abr", total_publicacoes: 65 + (hash % 30) },
    { mes: "Mai", total_publicacoes: 50 + (hash % 25) },
    { mes: "Jun", total_publicacoes: 45 + (hash % 30) },
  ];

  return {
    setor,
    setor_nome: setorNome,
    media_licitacoes_mes: baseMonthlyBids,
    valor_medio_contratos: baseAvgValue,
    top_orgaos: orgaos,
    sazonalidade: meses,
    total_empresas_entrantes: 20 + (hash % 40),
    tendencia_desconto: {
      desconto_medio_pct: descontoMedio,
      variacao_anual_pct: variacaoAnual,
    },
    last_updated: new Date().toISOString(),
  };
}

/** Backend proxy (commented out — stub in use) */
// async function proxyToBackend(setor: string, uf?: string): Promise<Response> {
//   const BACKEND_URL = process.env.BACKEND_URL || process.env.NEXT_PUBLIC_BACKEND_URL;
//   if (!BACKEND_URL) throw new Error("BACKEND_URL not configured");
//
//   const params = new URLSearchParams({ setor });
//   if (uf) params.set("uf", uf);
//
//   return fetch(`${BACKEND_URL}/v1/pseo/market-patterns?${params.toString()}`, {
//     headers: { "Content-Type": "application/json" },
//     next: { revalidate: 21600 },
//   });
// }

export async function GET(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const setor = searchParams.get("setor");

  if (!setor) {
    return NextResponse.json({ error: "setor is required" }, { status: 400 });
  }

  try {
    // When backend endpoint is available, replace with:
    // const resp = await proxyToBackend(setor);
    // if (!resp.ok) { return NextResponse.json({ message: await resp.text() }, { status: resp.status }); }
    // const data = await resp.json();

    const data = generateMockData(setor);

    return NextResponse.json(data, {
      headers: {
        "Cache-Control": "public, s-maxage=21600, stale-while-revalidate=43200",
      },
    });
  } catch {
    return NextResponse.json({ message: "Erro de conexão" }, { status: 502 });
  }
}

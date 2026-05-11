/**
 * @jest-environment node
 *
 * Regression test for sitemap fetch behavior.
 *
 * Historical context:
 *  - v1 (pre-SEO-460): awaits sequenciais → somou latência → HTTP 524.
 *  - v2 (SEO-460): Promise.all paraleliza + AbortSignal.timeout(15000).
 *  - v3 (#458, 2026-04-21): awaits sequenciais DE NOVO — 6 fetches paralelos
 *    saturavam o backend em produção (todos timeoutavam simultaneamente em ~30s+),
 *    resultando em sitemap/4.xml vazio. Serialização + ISR 1h (revalidate=3600)
 *    move o custo para 1 request/h por shard (amortizado entre crawlers).
 *  - v4 (SEO-COVERAGE-MANIFEST-001, #1039): Promise.all DE VOLTA — agora busca
 *    6 entidades + coverageManifest em paralelo. ISR 1h ainda amortiza; backend
 *    probe /health/live faz fail-open se backend indisponível.
 *
 * Por sub-sitemap:
 *  - id:2 → /v1/sitemap/licitacoes-indexable (1 endpoint)
 *  - id:4 → 6 endpoints de entidades + coverageManifest em Promise.all
 */

// Mock fetch globally (node env pattern — see __tests__/api/buscar.test.ts)
global.fetch = jest.fn();

// Env vars needed by sitemap()
process.env.BACKEND_URL = 'http://mock-backend';
process.env.NEXT_PUBLIC_CANONICAL_URL = 'https://smartlic.tech';

const ENTITY_ENDPOINTS = [
  '/v1/sitemap/cnpjs',
  '/v1/sitemap/contratos-orgao-indexable',
  '/v1/sitemap/orgaos',
  '/v1/sitemap/fornecedores-cnpj',
  '/v1/sitemap/municipios',
  '/v1/sitemap/itens',
] as const;

const PAYLOAD_BY_ENDPOINT: Record<string, object> = {
  '/v1/sitemap/licitacoes-indexable': { combos: [] },
  '/v1/sitemap/cnpjs': { cnpjs: [] },
  '/v1/sitemap/contratos-orgao-indexable': { orgaos: [] },
  '/v1/sitemap/orgaos': { orgaos: [] },
  '/v1/sitemap/fornecedores-cnpj': { cnpjs: [] },
  '/v1/sitemap/municipios': { slugs: [] },
  '/v1/sitemap/itens': { catmats: [] },
};

// Helper: importa sitemap fresco (sem cache de módulo) + mocks de filesystem
async function importSitemapFresh() {
  jest.resetModules();
  jest.mock('@/lib/blog', () => ({ getAllSlugs: () => [], getArticleBySlug: () => null }));
  jest.mock('@/lib/sectors', () => ({ SECTORS: [] }));
  jest.mock('@/lib/programmatic', () => ({
    generateSectorParams: () => [],
    generateLicitacoesParams: () => [],
    generateSectorUfParams: () => [],
  }));
  jest.mock('@/lib/cases', () => ({ getAllCaseSlugs: () => [] }));
  jest.mock('@/lib/cities', () => ({ CITIES: [] }));
  jest.mock('@/lib/glossary-terms', () => ({ GLOSSARY_TERMS: [] }));
  jest.mock('@/lib/authors', () => ({ getAllAuthorSlugs: () => [] }));
  jest.mock('@/lib/questions', () => ({ getAllQuestionSlugs: () => [] }));
  jest.mock('@/lib/masterclasses', () => ({ getAllMasterclassTemas: () => [] }));

  const mod = await import('../../app/sitemap');
  return mod.default;
}

function makeFastFetchMock() {
  (global.fetch as jest.Mock).mockImplementation(
    (url: string | URL | Request, _init?: RequestInit) => {
      const urlStr = typeof url === 'string' ? url : url.toString();
      // HOTFIX 2026-04-30: pre-flight probe /health/live precede entity fetches.
      if (urlStr.includes('/health/live')) {
        return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) } as Response);
      }
      const allEndpoints = [...ENTITY_ENDPOINTS, '/v1/sitemap/licitacoes-indexable'];
      const endpoint = allEndpoints.find((e) => urlStr.includes(e));
      const payload = endpoint ? PAYLOAD_BY_ENDPOINT[endpoint] : {};
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(payload),
      } as Response);
    },
  );
}

describe('sitemap() — fetch behavior (signal + parallelization)', () => {
  beforeEach(() => {
    (global.fetch as jest.Mock).mockReset();
  });

  it('sub-sitemap id:2 chama licitacoes-indexable com signal (AbortSignal.timeout)', async () => {
    makeFastFetchMock();
    const sitemap = await importSitemapFresh();
    await sitemap({ id: 2 });

    const call = (global.fetch as jest.Mock).mock.calls.find(([url]: [string]) =>
      url.includes('/v1/sitemap/licitacoes-indexable'),
    );
    expect(call).toBeDefined();
    const [, init] = call as [string, RequestInit | undefined];
    expect(init?.signal).toBeDefined();
  });

  it('sub-sitemap id:4 chama todos os 6 endpoints de entidades com signal (AbortSignal.timeout)', async () => {
    makeFastFetchMock();
    const sitemap = await importSitemapFresh();
    await sitemap({ id: 4 });

    for (const endpoint of ENTITY_ENDPOINTS) {
      const call = (global.fetch as jest.Mock).mock.calls.find(([url]: [string]) =>
        url.includes(endpoint),
      );
      expect(call).toBeDefined(); // endpoint foi chamado
      const [, init] = call as [string, RequestInit | undefined];
      // Regression guard: ausência de signal era o bug original (faltava AbortSignal.timeout)
      expect(init?.signal).toBeDefined();
    }
  });

  it('sub-sitemap id:4 paraleliza os 6 fetches de entidades via Promise.all (SEO-COVERAGE-MANIFEST-001)', async () => {
    // SEO-COVERAGE-MANIFEST-001 (#1039): código migrou de awaits sequenciais → Promise.all
    // para buscar as 6 listas de entidades + coverageManifest em paralelo.
    // Garantia: todos os 6 endpoints de entidade são iniciados antes que qualquer um resolva,
    // confirmando que o fetch é verdadeiramente paralelo (não serial).
    const initiated: string[] = [];
    const resolvers: Array<() => void> = [];

    (global.fetch as jest.Mock).mockImplementation(
      (url: string | URL | Request) => {
        const urlStr = typeof url === 'string' ? url : url.toString();
        // HOTFIX 2026-04-30: probe /health/live precede entity fetches; resolve sync.
        if (urlStr.includes('/health/live')) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve({ ok: true }) } as Response);
        }
        // coverage-manifest resolves sync (not an entity endpoint under test)
        if (urlStr.includes('/v1/seo/coverage-manifest')) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve({}) } as Response);
        }
        const endpoint = ENTITY_ENDPOINTS.find((e) => urlStr.includes(e));
        if (endpoint) {
          initiated.push(endpoint);
          return new Promise<Response>((resolve) => {
            resolvers.push(() =>
              resolve({
                ok: true,
                json: () => Promise.resolve(PAYLOAD_BY_ENDPOINT[endpoint]),
              } as Response),
            );
          });
        }
        return Promise.resolve({ ok: false, json: () => Promise.resolve({}) } as Response);
      },
    );

    const sitemap = await importSitemapFresh();
    const sitemapPromise = sitemap({ id: 4 });

    const flush = async () => {
      for (let i = 0; i < 20; i++) await Promise.resolve();
    };

    // Parallel: após microtasks iniciais, TODOS os 6 fetches devem estar em voo
    await flush();
    expect(initiated.length).toBe(ENTITY_ENDPOINTS.length);

    // Resolve todos para completar a promise
    resolvers.forEach((resolve) => resolve());
    await sitemapPromise;
  });
});

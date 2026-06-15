# CDN Strategy — Cache de Assets Estaticos e API Responses

## Visao Geral

Este documento descreve a estrategia de CDN (Content Delivery Network) do SmartLic,
implementada via **Issue #1868** e **Cloudflare free tier**.

### Objetivos

| Meta | Alvo | Metrica |
|------|------|---------|
| Latencias de assets estaticos | p50 < 50ms em qualquer regiao do Brasil | Lighthouse / RUM |
| Cache hit ratio | > 90% para assets estaticos | Cloudflare Analytics |
| Tempo de purge apos deploy | < 30s | Workflow duration |
| Core Web Vitals | Sem degradacao pos-CDN | Lighthouse CI / CrUX |

---

## 1. Arquitetura CDN

```
Usuario (BR)
    |
    v
Cloudflare CDN (edge cache)
    |  (cache hit: serve direto do edge)
    |  (cache miss: faz fetch do origin e cacheia)
    v
Railway Origin (Next.js + FastAPI)
```

### Provedor: Cloudflare Free Tier

- **Custo:** Gratuito (free tier inclui CDN ilimitado, SSL, DDoS protection)
- **Configuracao:** DNS proxy (laranja) para `smartlic.tech`
- **Por que Cloudflare:** Ja utilizado no stack (CSP allowlists incluem `cloudflare.com`,
  `cdnjs.cloudflare.com`, `static.cloudflareinsights.com`); free tier robusto para o
  volume atual (~10k+ paginas SEO, ~25 paginas core)

### Alternativa: Railway Edge

- Railway nao oferece edge caching nativo — todo request vai ao origin.
- Cloudflare e a unica opcao viavel para caching geografico no stack atual.

---

## 2. Cache-Control Strategy

### 2.1 Assets Estaticos (AC2)

| Path | Cache-Control | CDN Edge | Browser | Fundamento |
|------|---------------|----------|---------|------------|
| `/_next/static/*` | `public, max-age=31536000, immutable` | 1 ano | 1 ano | Fingerprint em URL (build ID unico por deploy) — nunca expira |
| `/fonts/*` | `public, max-age=31536000, immutable` | 1 ano | 1 ano | Raramente mudam; mesma estrategia do static |
| `/images/*` | `public, max-age=604800, stale-while-revalidate=86400` | 7 dias + 24h stale | 7 dias | Podem ser substituidas sem mudar URL |
| `public/*.txt,ico,xml,json,pdf,svg` | `public, max-age=3600, stale-while-revalidate=86400` | 1h + 24h stale | 1h | Sem fingerprint; stale-while-revalidate evita revalidacao massiva |

### 2.2 APIs Publicas (AC2)

| Path | Cache-Control | CDN Edge | Fundamento |
|------|---------------|----------|------------|
| `/v1/sitemap/*` | `public, max-age=21600, stale-while-revalidate=43200, stale-if-error=86400` | 6h + 12h stale | Mutacao maxima 1x/dia (ingestion) |
| `/v1/*_publicos` | `public, max-age=3600, stale-while-revalidate=86400, stale-if-error=86400` | 1h + 24h stale | Ingestion 3x/dia; stale cobre intervalos |
| `/health` | No-cache | Nao cacheia | Deve refletir estado real |

### 2.3 HTML Pages (AC2)

| Path | Cache-Control | CDN Edge | Fundamento |
|------|---------------|----------|------------|
| HTML publicas (`/blog/*`, `/licitacoes/*`, etc.) | `public, max-age=0, s-maxage=3600, stale-while-revalidate=3600` | 1h + 1h stale | CDN cacheia 1h; browser sempre revalida |
| Paginas protegidas (`/buscar`, `/conta`, etc.) | `private, no-cache` | Nao cacheia | Dados do usuario; nunca em CDN |

**Nota:** Security headers (CSP, HSTS, X-Frame-Options) sao aplicados pelo
`middleware.ts` em todas as rotas HTML — a CDN nao os remove (AC4). Para assets
estaticos, security headers nao sao necessarios pois nao executam contexto HTML.

---

## 3. Cache Invalidation (AC3)

### 3.1 Automatic Post-Deploy

O workflow `.github/workflows/cdn-purge.yml` executa automaticamente apos
cada deploy bem-sucedido do Railway (`deploy.yml` → `workflow_run`).

**Sequencia:**
1. Deploy atinge Railway (backend + frontend)
2. Smoke tests passam
3. `cdn-purge.yml` dispara automaticamente
4. Cloudflare API purge `purge_everything=true`
5. CDN edges worldwide invalidam cache em ~5s

### 3.2 Manual Purge

Opcoes via `workflow_dispatch`:

| Purge Type | Escopo | Quando usar |
|------------|--------|-------------|
| `all` | Tudo (default) | Deploy, mudanca global |
| `static` | `/_next/static/*`, `/images/*`, `/fonts/*`, `public/*` | Rollback de assets |
| `api-public` | `/api/*`, `/sitemap/*`, `/health` | Correcao de dados publicos |

### 3.3 Build ID Invalidation

Para `/_next/static/*`, a invalidacao e nativa: cada deploy gera um build ID unico
(`build-{timestamp}-{random}`) via `generateBuildId` em `next.config.js`. Assets
antigos nunca sao servidos porque a URL mudou. O CDN purge e necessario apenas
para HTML, imagens, e outros paths sem fingerprint.

---

## 4. Security Headers (AC4)

A CDN **nao remove** security headers aplicados pelo origin:

| Header | Onde e Aplicado | Afetado por CDN? |
|--------|-----------------|-------------------|
| Content-Security-Policy | `middleware.ts` | Nao — CDN passa headers |
| Strict-Transport-Security | `middleware.ts` | Nao — HSTS e edge-level |
| X-Frame-Options | `middleware.ts` | Nao |
| X-Content-Type-Options | `middleware.ts` | Nao |
| Cache-Control | `next.config.js` + `middleware.ts` + `_sitemap_cache_headers.py` | Gerenciado por nos |

**Cloudflare especifico:** Por padrao, Cloudflare nao modifica headers de resposta.
A configuracao "Email Address Obfuscation" e "Rocket Loader" devem estar desligadas
para evitar injecao de JS indesejado.

---

## 5. Metricas (AC5)

### 5.1 Cloudflare Analytics (nativo)

| Metrica | Onde Ver | Target |
|---------|----------|--------|
| `cdn_cache_hit_ratio` | Cloudflare Dashboard > Analytics > Performance | > 90% |
| `cdn_bandwidth_saved_bytes` | Cloudflare Dashboard > Analytics > Traffic | N/A (monitorar tendencia) |
| `cdn_response_time_ms` | Cloudflare Dashboard > Analytics > Performance | < 50ms p50 |

### 5.2 Custom Metrics (via X-CDN-Strategy header)

Cada tipo de conteudo tem um header `X-CDN-Strategy` que identifica a estrategia
de cache aplicada:

```
X-CDN-Strategy: immutable-1y     → _next/static/*
X-CDN-Strategy: images-7d        → /images/*
X-CDN-Strategy: fonts-1y         → /fonts/*
X-CDN-Strategy: sitemap-1h       → /sitemap/*
X-CDN-Strategy: public-assets-1h → public/*.txt|ico|xml|json|pdf|svg
```

### 5.3 CI Metric

O workflow `cdn-purge.yml` expoe a metrica `cdn_purge_count{type="...",status="..."}`
para consumo via Prometheus/Grafana ou GitHub Actions analytics.

---

## 6. Core Web Vitals (AC6)

A CDN melhora (nao degrada) CWV:

| Metrica | Impacto CDN | Mecanismo |
|---------|-------------|-----------|
| LCP | Melhora | HTML + imagens servidos do edge (menor TTFB) |
| FID/INP | Neutro | JS bundles estao em `_next/static/` com cache 1y |
| CLS | Neutro | CDN nao afeta layout shift |

**Monitoramento:** Lighthouse CI (`.github/workflows/lighthouse.yml`) + Chrome User
Experience Report (CrUX) via Google Search Console.

---

## 7. Setup e Configuracao

### 7.1 Cloudflare DNS

Dominio `smartlic.tech` deve estar com DNS proxied by Cloudflare (laranja):

| Record | Type | Content | Proxy |
|--------|------|---------|-------|
| `smartlic.tech` | CNAME | `smartlic.railway.app` | Proxied (laranja) |
| `www.smartlic.tech` | CNAME | `smartlic.railway.app` | Proxied (laranja) |
| `api.smartlic.tech` | CNAME | `smartlic-api.railway.app` | Proxied (laranja) |

### 7.2 GitHub Secrets

Para habilitar purge automatico, configurar no GitHub Actions:

| Secret/Var | Descricao | Onde Obter |
|------------|-----------|------------|
| `CLOUDFLARE_API_TOKEN` | API token com permissao Zone.Cache Purge | Cloudflare Dashboard > My Profile > API Tokens |
| `CLOUDFLARE_ZONE_ID` | Zone ID do dominio | Cloudflare Dashboard > Overview > Zone ID |

### 7.3 Cloudflare Settings Recomendados

| Setting | Valor | Justificativa |
|---------|-------|---------------|
| SSL/TLS > SSL | Full (strict) | Requer certificado valido no origin Railway |
| Speed > Auto Minify | Desligado | Minificacao do Next.js e suficiente; Auto Minify pode quebrar JS |
| Speed > Brotli | Ligado | Compressao nativa Cloudflare |
| Caching > Cache Level | Standard | Respeita headers Cache-Control do origin |
| Caching > Edge Cache TTL | Respect Origin | Usar nossos headers, nao override |
| Scrape Shield > Email Obfuscation | Desligado | Nao usar emails em texto plano |
| Scrape Shield > Hotlink Protection | Desligado | Imagens publicas para SEO |

---

## 8. Custos

| Componente | Custo | Detalhes |
|------------|-------|----------|
| Cloudflare Free Tier | Gratuito | CDN, SSL, DDoS, 3 page rules |
| API Purge Requests | Gratuito | Ilimitado no free tier |
| Banda CDN | Gratuito | Ilimitado (sujeito a uso aceitavel) |
| **Total** | **R$ 0,00** | Nenhum custo adicional |

---

## 9. Troubleshooting

### Cache nao esta sendo purgado

1. Verificar se `CLOUDFLARE_API_TOKEN` tem permissao `zone:cache:purge`
2. Verificar se `CLOUDFLARE_ZONE_ID` esta correto (copiar do dashboard)
3. Rodar purge manual via GitHub Actions > `cdn-purge.yml` > `workflow_dispatch`
4. Verificar logs do workflow para erro HTTP da API

### CDN nao esta cacheando

1. Verificar se DNS esta proxied (laranja) no Cloudflare Dashboard
2. Verificar se `Cache-Control` header tem `s-maxage` ou `public`
3. Verificar Cloudflare > Caching > Cache Level = Standard
4. Verificar se response nao tem `Set-Cookie` (CDN nao cacheia respostas com cookie)

### LCP continua alto

1. Verificar se HTML esta sendo cacheado (header `CF-Cache-Status: HIT`)
2. Verificar se imagens estao otimizadas (next/image com AVIF/WebP)
3. Verificar Lighthouse > Diagnostics > Minimize main-thread work

---

## 10. Referencias

- [Cloudflare Cache Documentation](https://developers.cloudflare.com/cache/)
- [Next.js CDN Optimization](https://nextjs.org/docs/app/building-your-application/deploying#cdn-support)
- [Cache-Control Best Practices](https://web.dev/articles/http-cache)
- Issue #1868 — Implementacao desta estrategia
- Workflow: `.github/workflows/cdn-purge.yml`
- Config: `frontend/next.config.js` (headers)
- Config: `frontend/middleware.ts` (HTML pages)
- Config: `backend/routes/_sitemap_cache_headers.py` (API headers)

---

_Atualizado: 2026-06-15_

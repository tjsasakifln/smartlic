"""STORY-SEO-015 + Issue #1868: Cache-Control headers compartilhados.

STORY-SEO-015: Headers para endpoints /v1/sitemap/*.
Habilita CDN/proxy intermediarios (Cloudflare, browsers, crawlers) a cachear
respostas por 6h fresh + 12h stale-while-revalidate + 24h stale-if-error.

Issue #1868 AC2: Headers padronizados para APIs publicas (/v1/*_publicos)
com max-age=3600 (1h) + stale-while-revalidate=86400 (24h).

Reduz carga no backend (WEB_CONCURRENCY=2) durante crawler bursts (Googlebot
parallelism pode atingir 10+ conexoes simultaneas em endpoint sitemap).

Uso em handler:

    from fastapi import Response
    from routes._sitemap_cache_headers import SITEMAP_CACHE_HEADERS, PUBLIC_API_CACHE_HEADERS

    @router.get("/sitemap/foo", ...)
    async def sitemap_foo(response: Response):
        response.headers.update(SITEMAP_CACHE_HEADERS)
        ...

    @router.get("/v1/alertas/...", ...)
    async def alertas_endpoint(response: Response):
        response.headers.update(PUBLIC_API_CACHE_HEADERS)
        ...
"""

# STORY-SEO-015: 6h fresh (max-age=21600) + 12h stale-while-revalidate + 24h stale-if-error.
# Tradeoffs:
#   - 6h fresh: ingestion daily 2am BRT; sitemap muda <=1x/dia. 6h evita over-stale
#     entre ingestion (max 1 ciclo perdido).
#   - stale-while-revalidate=43200 (12h): CDN serve stale + dispara refresh em
#     background. Crawler nunca ve timeout enquanto backend gera nova versao.
#   - stale-if-error=86400 (24h): se backend 5xx, CDN serve stale por ate 24h.
#     Crawler nao detecta erros transientes.
SITEMAP_CACHE_HEADERS = {
    "Cache-Control": "public, max-age=21600, stale-while-revalidate=43200, stale-if-error=86400",
    "Vary": "Accept-Encoding",
}

# Issue #1868 AC2: APIs publicas com cache de 1h + stale-while-revalidate 24h.
# Tradeoffs:
#   - max-age=3600 (1h): dados publicos (alertas, municipios, contratos, etc.)
#     mudam no maximo a cada ingestion cycle (3x/dia). 1h evita over-stale
#     sem sobrecarregar o backend.
#   - stale-while-revalidate=86400 (24h): CDN serve stale + refresh background.
#     Crawlers nunca veem timeout mesmo se backend estiver sob carga.
#   - stale-if-error=86400 (24h): se backend 5xx transiente, CDN serve stale
#     por ate 24h. Crawlers nao detectam erros temporarios.
# NOTA: Nao inclui Vary: Accept-Encoding porque FastAPI ja gerencia
# compressao automaticamente via Starlette/Middleware.
PUBLIC_API_CACHE_HEADERS = {
    "Cache-Control": "public, max-age=3600, stale-while-revalidate=86400, stale-if-error=86400",
}

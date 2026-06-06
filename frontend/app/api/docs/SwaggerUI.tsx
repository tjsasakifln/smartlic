'use client';

import { useEffect, useRef } from 'react';

/**
 * API-SELF-005: Swagger UI renderizado no cliente usando swagger-ui-dist do CDN.
 *
 * Aponta para o /openapi.json do backend, que documenta todos os endpoints
 * públicos da API incluindo autenticação por X-API-Key.
 *
 * Acesso público — não requer JWT. A página em si é acessível sem auth.
 */

const BACKEND_ORIGIN = process.env.NEXT_PUBLIC_API_URL || 'https://api.smartlic.tech';
const SWAGGER_CSS = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css';
const SWAGGER_JS = 'https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js';

export function SwaggerUI() {
  const containerRef = useRef<HTMLDivElement>(null);
  const loadedRef = useRef(false);

  useEffect(() => {
    if (loadedRef.current || !containerRef.current) return;
    loadedRef.current = true;

    // Inject Swagger UI CSS
    const linkEl = document.createElement('link');
    linkEl.rel = 'stylesheet';
    linkEl.href = SWAGGER_CSS;
    document.head.appendChild(linkEl);

    // Load Swagger UI JS and initialize
    const scriptEl = document.createElement('script');
    scriptEl.src = SWAGGER_JS;
    scriptEl.onload = () => {
      const SwaggerUIBundle = (window as any).SwaggerUIBundle;
      if (!SwaggerUIBundle || !containerRef.current) return;

      SwaggerUIBundle({
        url: `${BACKEND_ORIGIN}/openapi.json`,
        dom_id: '#swagger-ui-container',
        deepLinking: true,
        presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
        layout: 'StandaloneLayout',
        defaultModelsExpandDepth: -1,
        docExpansion: 'list',
        filter: true,
        tryItOutEnabled: true,
        requestInterceptor: (req: any) => {
          // Add CORS-safe mode for interactive "Try it out"
          if (req.url.startsWith(BACKEND_ORIGIN)) {
            // Keep the request as-is; the browser handles CORS
          }
          return req;
        },
      });
    };
    document.body.appendChild(scriptEl);

    return () => {
      // Cleanup on unmount
      if (linkEl.parentNode) linkEl.parentNode.removeChild(linkEl);
      if (scriptEl.parentNode) scriptEl.parentNode.removeChild(scriptEl);
    };
  }, []);

  return (
    <div className="min-h-screen bg-[var(--canvas)]">
      {/* Top bar */}
      <div className="bg-brand-navy text-white py-3 px-4 sm:px-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <a href="/api" className="text-white/70 hover:text-white text-sm transition-colors">
            ← API
          </a>
          <span className="text-white/30">|</span>
          <span className="font-semibold text-sm">SmartLic API v1</span>
        </div>
        <a
          href={`${BACKEND_ORIGIN}/openapi.json`}
          target="_blank"
          rel="noopener noreferrer"
          className="text-white/70 hover:text-white text-xs transition-colors"
        >
          openapi.json
        </a>
      </div>

      {/* Swagger UI container */}
      <div
        id="swagger-ui-container"
        ref={containerRef}
        className="swagger-ui-root"
      />
    </div>
  );
}

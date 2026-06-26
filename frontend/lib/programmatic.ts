/**
 * PSEO-002: Este arquivo agora é um re-export barrel para lib/programmatic/.
 *
 * O conteúdo foi extraído para:
 *   - lib/programmatic/types.ts   — tipos, constantes, utilitários, fetchers
 *   - lib/programmatic/editorial.ts — conteúdo editorial e geradores de FAQ
 *   - lib/programmatic/index.ts   — barrel re-export
 *
 * Fases seguintes (PSEO-001, PSEO-006) farão a migração dos consumidores
 * e a remoção definitiva deste arquivo.
 */

// NOTE: O barrel intencionalmente re-exporta TUDO do módulo para manter
// compatibilidade com imports existentes de '@/lib/programmatic'.
export * from './programmatic/index';

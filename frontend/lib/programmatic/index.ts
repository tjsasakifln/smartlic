/**
 * PSEO-002: Barrel re-export para lib/programmatic/.
 *
 * Re-exporta todas as exports públicas de types.ts e editorial.ts.
 * Consumidores continuam usando `import { ... } from '@/lib/programmatic'`.
 */
export * from './types';
export * from './editorial';

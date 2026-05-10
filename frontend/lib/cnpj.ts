/**
 * CNPJ format validation — alfanumérico-ready para IN 2.229/2024.
 *
 * A Receita Federal IN 2.229/2024 introduz CNPJs alfanuméricos
 * (12 chars [A-Z0-9] + 2 dígitos verificadores) com vigência a partir de 01/07/2026.
 * Este módulo centraliza a validação de formato no frontend, eliminando checks
 * `length === 14` que rejeitarão CNPJs alfanuméricos futuros.
 *
 * Uso:
 *   import { isValidCnpjFormat, normalizeCnpj } from '@/lib/cnpj';
 *   if (isValidCnpjFormat('12.345.678/0001-95')) { ... }
 *   if (isValidCnpjFormat('AB3DEF78000195')) { ... }  // alfanumérico futuro
 */

const CNPJ_PATTERN = /^[A-Z0-9]{12}\d{2}$/i;
const CPF_PATTERN = /^\d{11}$/;

/**
 * Valida formato CNPJ — alfanumérico-ready para 01/07/2026 (IN 2.229/2024).
 *
 * Aceita:
 * - CNPJ numérico sem máscara: "12345678000195" (14 dígitos)
 * - CNPJ alfanumérico futuro: "AB3DEF78000195" (12 alnum + 2 dígitos)
 * - CNPJ com máscara padrão: "12.345.678/0001-95"
 *
 * Rejeita:
 * - CPF (11 dígitos puramente numéricos)
 * - Strings com menos ou mais de 14 chars úteis após remover máscara
 * - Valores nulos, vazios ou não-string
 */
export function isValidCnpjFormat(s: string | null | undefined): boolean {
  if (!s || typeof s !== 'string') return false;
  const clean = s.replace(/[.\-\/]/g, '').toUpperCase();
  return CNPJ_PATTERN.test(clean) && !CPF_PATTERN.test(clean);
}

/**
 * Remove formatação, retorna string limpa uppercase.
 *
 * "12.345.678/0001-95" → "12345678000195"
 * "ab3def78000195"     → "AB3DEF78000195"
 * ""                   → ""
 */
export function normalizeCnpj(s: string | null | undefined): string {
  return (s ?? '').replace(/[^A-Z0-9]/gi, '').toUpperCase();
}

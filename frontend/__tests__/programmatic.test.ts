import { formatBRLCompact, formatBRL, backendIdToFrontendSlug, BACKEND_ID_TO_FRONTEND_SLUG } from '@/lib/programmatic';

describe('formatBRLCompact', () => {
  // AC5: >= R$1B → compact "bi"
  it('formata bilhões com sufixo "bi"', () => {
    expect(formatBRLCompact(10_849_085_800)).toBe('R$10,8 bi');
  });

  it('formata exatamente R$1B', () => {
    expect(formatBRLCompact(1_000_000_000)).toBe('R$1,0 bi');
  });

  // AC6: >= R$1M → compact "mi"
  it('formata milhões com sufixo "mi"', () => {
    expect(formatBRLCompact(1_500_000)).toBe('R$1,5 mi');
  });

  it('formata exatamente R$1M', () => {
    expect(formatBRLCompact(1_000_000)).toBe('R$1,0 mi');
  });

  it('formata R$999.999 sem compact (abaixo de 1M)', () => {
    expect(formatBRLCompact(999_999)).toBe('R$\u00A0999.999');
  });

  // AC7: < R$1M → comportamento igual ao formatBRL (sem compact)
  it('formata R$750.000 sem compact notation', () => {
    expect(formatBRLCompact(750_000)).toBe(formatBRL(750_000));
  });

  it('formata zero sem compact notation', () => {
    expect(formatBRLCompact(0)).toBe(formatBRL(0));
  });

  it('formata R$500M (teto do cap de outlier) corretamente', () => {
    expect(formatBRLCompact(500_000_000)).toBe('R$500,0 mi');
  });
});

// SEO-643: backendIdToFrontendSlug normalisation
describe('backendIdToFrontendSlug', () => {
  it('maps explicit exceptions (many-to-one backend IDs)', () => {
    expect(backendIdToFrontendSlug('software_desenvolvimento')).toBe('software');
    expect(backendIdToFrontendSlug('software_licencas')).toBe('software');
    expect(backendIdToFrontendSlug('servicos_prediais')).toBe('facilities');
    expect(backendIdToFrontendSlug('produtos_limpeza')).toBe('facilities');
    expect(backendIdToFrontendSlug('medicamentos')).toBe('saude');
    expect(backendIdToFrontendSlug('equipamentos_medicos')).toBe('saude');
    expect(backendIdToFrontendSlug('insumos_hospitalares')).toBe('saude');
    expect(backendIdToFrontendSlug('transporte_servicos')).toBe('transporte');
    expect(backendIdToFrontendSlug('frota_veicular')).toBe('transporte');
  });

  it('converts underscores to hyphens for hyphenated slugs', () => {
    expect(backendIdToFrontendSlug('manutencao_predial')).toBe('manutencao-predial');
    expect(backendIdToFrontendSlug('engenharia_rodoviaria')).toBe('engenharia-rodoviaria');
    expect(backendIdToFrontendSlug('materiais_eletricos')).toBe('materiais-eletricos');
    expect(backendIdToFrontendSlug('materiais_hidraulicos')).toBe('materiais-hidraulicos');
  });

  it('returns identity for IDs that match their slug', () => {
    expect(backendIdToFrontendSlug('vestuario')).toBe('vestuario');
    expect(backendIdToFrontendSlug('informatica')).toBe('informatica');
    expect(backendIdToFrontendSlug('engenharia')).toBe('engenharia');
    expect(backendIdToFrontendSlug('vigilancia')).toBe('vigilancia');
  });

  it('BACKEND_ID_TO_FRONTEND_SLUG covers all 9 explicit exceptions', () => {
    expect(Object.keys(BACKEND_ID_TO_FRONTEND_SLUG)).toHaveLength(9);
  });
});

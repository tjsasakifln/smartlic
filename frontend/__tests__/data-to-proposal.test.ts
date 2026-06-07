/**
 * Tests for data-to-proposal mapping utility — CONV-010-2 (#1509)
 */

import { mapEntityToProposal } from '../app/components/conversion/data-to-proposal';

describe('mapEntityToProposal', () => {
  describe('fornecedor', () => {
    it('maps fornecedor data correctly', () => {
      const result = mapEntityToProposal('fornecedor', 'ABC Ltda', {
        total_contratos: 42,
        valor_total: 2500000,
        ufs_atuantes: 'SP, RJ, MG',
      });

      expect(result.valueProp).toBe(
        'Quer vencer mais licitações como ABC Ltda?',
      );
      expect(result.supportingDetail).toContain('concorrencial');
      expect(result.insights).toHaveLength(3);

      // Check first insight
      expect(result.insights[0]).toMatchObject({
        label: 'Contratos Ganhos',
        value: '42',
        icon: 'chart',
      });

      // Check value extraction with fallback
      expect(result.insights[1].value).toBe('2500000');
    });

    it('uses fallback values when data is missing', () => {
      const result = mapEntityToProposal('fornecedor', 'ABC Ltda', {});

      result.insights.forEach((insight) => {
        expect(insight.value).toBe('—');
      });
    });
  });

  describe('orgao', () => {
    it('maps orgao data correctly', () => {
      const result = mapEntityToProposal('orgao', 'Prefeitura de SP', {
        total_licitacoes: 15,
        contratos_ativos: 8,
        valor_total_estimado: 5000000,
      });

      expect(result.valueProp).toBe(
        'Quer vender para Prefeitura de SP?',
      );
      expect(result.insights).toHaveLength(3);
      expect(result.insights[0].label).toBe('Editais Abertos');
      expect(result.insights[0].value).toBe('15');
    });
  });

  describe('cnpj', () => {
    it('maps cnpj data correctly', () => {
      const result = mapEntityToProposal('cnpj', '12.345.678/0001-90', {
        participacoes: 25,
        contratos_obtidos: 10,
        presenca_geografica: 'SP, RJ',
      });

      expect(result.valueProp).toContain('Dados completos do CNPJ');
      expect(result.insights).toHaveLength(3);
      expect(result.insights[0].label).toBe('Participações');
      expect(result.insights[0].value).toBe('25');
    });
  });

  describe('setor', () => {
    it('maps setor data correctly', () => {
      const result = mapEntityToProposal('setor', 'Tecnologia da Informação', {
        total_oportunidades: 120,
        principais_orgaos: 'Ministérios, Prefeituras',
        valor_medio: 350000,
      });

      expect(result.valueProp).toBe(
        'Atue em Tecnologia da Informação com inteligência',
      );
      expect(result.insights).toHaveLength(3);
      expect(result.insights[0].label).toBe('Editais no Setor');
      expect(result.insights[0].value).toBe('120');
    });
  });

  describe('municipio', () => {
    it('maps municipio data correctly', () => {
      const result = mapEntityToProposal('municipio', 'São Paulo', {
        total_editais: 200,
        setores_principais: 'Saúde, Educação',
        volume_contratacoes: 'R$ 50M',
      });

      expect(result.valueProp).toBe('Licitações em São Paulo');
      expect(result.insights).toHaveLength(3);
      expect(result.insights[0].label).toBe('Editais Municipais');
    });
  });

  describe('contrato', () => {
    it('maps contrato data correctly', () => {
      const result = mapEntityToProposal('contrato', 'Contrato 001/2025', {
        renovacoes_previstas: 3,
        concorrentes_ativos: 5,
        valor_similar: 'R$ 2.5M',
      });

      expect(result.valueProp).toContain('Contratos como este em');
      expect(result.insights).toHaveLength(3);
      expect(result.insights[0].label).toBe('Renovações');
      expect(result.insights[0].value).toBe('3');
    });
  });

  describe('fallback', () => {
    it('returns fallback for unknown entityType', () => {
      const result = mapEntityToProposal('unknown', 'Entidade', {});

      expect(result.valueProp).toBe('Análise inteligente para Entidade');
      expect(result.insights).toHaveLength(1);
      expect(result.insights[0].label).toBe('Oportunidades');
    });
  });
});

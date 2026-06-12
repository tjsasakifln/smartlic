'use client';

import React from 'react';

export default function NetworkAnalyticsSection() {
  return (
    <section className="mb-8">
      <h2 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
        Dados de Uso Agregados (Network Analytics)
      </h2>

      <p className="text-gray-700 dark:text-gray-300 leading-relaxed mb-4">
        A SmartLic coleta dados de uso agregados e anonimizados para gerar
        sinais de mercado que beneficiam todos os usuários da plataforma.
        Esta coleta segue os princípios da LGPD (Lei 13.709/2018),
        priorizando a privacidade e a transparência.
      </p>

      <div className="overflow-x-auto mb-4">
        <table className="min-w-full text-sm border border-gray-200 dark:border-gray-700">
          <thead>
            <tr className="bg-gray-100 dark:bg-gray-700">
              <th className="px-4 py-3 text-left font-semibold text-gray-900 dark:text-white border-b">Aspecto</th>
              <th className="px-4 py-3 text-left font-semibold text-gray-900 dark:text-white border-b">Detalhe</th>
            </tr>
          </thead>
          <tbody className="text-gray-700 dark:text-gray-300">
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <td className="px-4 py-3"><strong>O que coletamos</strong></td>
              <td className="px-4 py-3">
                Tipo de evento (busca por setor, visualizacao de orgao,
                consulta de CNPJ), contagem de eventos, unidade federativa (UF),
                setor economico, modalidade de licitacao (apenas dados
                agregados — jamais individuais)
              </td>
            </tr>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <td className="px-4 py-3"><strong>O que NAO coletamos</strong></td>
              <td className="px-4 py-3">
                CNPJ, CPF, nome, email, endereco IP, user-agent,
                fingerprint de dispositivo, dados de navegacao individual,
                session ID, ou qualquer dado pessoal identificavel (PII)
              </td>
            </tr>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <td className="px-4 py-3"><strong>Finalidade (Art. 6, I)</strong></td>
              <td className="px-4 py-3">
                Gerar sinais de mercado agregados para beneficio coletivo:
                identificar tendencias setoriais, demanda regional, e
                padroes de contratacao publica. Os dados ajudam todos os
                usuarios a tomar decisoes mais informadas.
              </td>
            </tr>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <td className="px-4 py-3"><strong>Base legal</strong></td>
              <td className="px-4 py-3">
                Consentimento explicito do titular (Art. 7, I da LGPD) —
                opt-in ativo, nunca presumido
              </td>
            </tr>
            <tr className="border-b border-gray-200 dark:border-gray-700">
              <td className="px-4 py-3"><strong>Periodo de retencao</strong></td>
              <td className="px-4 py-3">
                365 dias para dados diarios, 730 dias (2 anos) para
                agregados semanais
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4">
        <p className="text-gray-700 dark:text-gray-300">
          <strong>Como desabilitar:</strong> Voce pode alterar sua preferencia
          de contribuicao a qualquer momento em{' '}
          <a
            href="/configuracoes#privacidade"
            className="text-blue-600 dark:text-blue-400 hover:underline"
          >
            Configuracoes &gt; Privacidade
          </a>
          . A coleta so ocorre com seu consentimento explicito (opt-in).
          A qualquer momento, voce pode revogar o consentimento e os dados
          agregados existentes serao mantidos apenas na forma anonimizada.
        </p>
      </div>
    </section>
  );
}

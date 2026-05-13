import Link from 'next/link';
import { getUfPrep, formatBRLCompact } from '@/lib/programmatic';

/**
 * ZeroEditalsCTA — CTA especializado para páginas programáticas sem editais ativos.
 *
 * Quando totalEditais30d === 0, substitui o CTA genérico por mensagem que
 * destaca o volume de contratos históricos e oferece alerta de novos editais.
 * Regra de arquitetura: NUNCA liderar com "0 editais", SEMPRE liderar com
 * volume de contratos 12 meses + CTA de alerta.
 */

interface ZeroEditalsCTAProps {
  setor: string;
  uf: string;
  /** 2-letter UF code — used to determine the correct preposition */
  ufCode?: string;
  slug: string;
  contractsCount: number;
  contractsTotalValue: number;
  contractsAvgValue?: number;
}

export default function ZeroEditalsCTA({
  setor,
  uf,
  ufCode,
  slug,
  contractsCount,
  contractsTotalValue,
  contractsAvgValue,
}: ZeroEditalsCTAProps) {
  const setorEncoded = encodeURIComponent(setor);
  const ufEncoded = ufCode ? encodeURIComponent(ufCode) : '';
  const prep = uf ? ` ${getUfPrep(ufCode)} ${uf}` : '';

  return (
    <div className="not-prose mt-12 mb-8 bg-gradient-to-br from-brand-navy to-brand-blue rounded-xl p-6 sm:p-8 text-white text-center">
      <h3 className="text-xl sm:text-2xl font-bold mb-3">
        Nenhum edital de {setor} aberto agora{prep} — mas n&atilde;o significa que n&atilde;o h&aacute; oportunidade
      </h3>
      <p className="text-white/80 mb-4 max-w-xl mx-auto">
        Nos &uacute;ltimos 12 meses: {contractsCount.toLocaleString('pt-BR')} contratos, R$ {formatBRLCompact(contractsTotalValue)} movimentados
        {contractsAvgValue ? `, valor médio de R$ ${formatBRLCompact(contractsAvgValue)}` : ''}.
        Quem estava preparado levou.
      </p>
      <p className="text-white/60 text-sm mb-6 max-w-xl mx-auto">
        Voc&ecirc; recebe um email quando novos editais abrirem. Em m&eacute;dia, nossos usu&aacute;rios s&atilde;o alertados 3 dias antes da publica&ccedil;&atilde;o oficial.
      </p>
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <Link
          href={`/alertas?setor=${setorEncoded}&uf=${ufEncoded}&source=blog-zero-edital`}
          className="inline-block bg-white text-brand-navy font-semibold px-6 py-3 rounded-button transition-all hover:scale-[1.02] active:scale-[0.98]"
        >
          Criar alerta para {setor}{prep}
        </Link>
        <Link
          href={`/contratos?setor=${setorEncoded}&uf=${ufEncoded}`}
          className="inline-block bg-white/20 text-white font-semibold px-6 py-3 rounded-button transition-all hover:bg-white/30 hover:scale-[1.02] active:scale-[0.98]"
        >
          Ver contratos ativos de {setor}{prep}
        </Link>
      </div>
    </div>
  );
}

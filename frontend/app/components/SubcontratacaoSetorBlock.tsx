"use client";
/**
 * SubcontratacaoSetorBlock — Issue #1321
 *
 * Block for sector pages like /licitacoes/[setor]:
 * "X% das empresas vencedoras neste setor subcontratam"
 * CTA: link to /subcontratacao flagship page.
 *
 * Tenta buscar dados de um endpoint público; se indisponível, mostra
 * placeholder estático com CTA.
 */

import { useEffect, useState } from "react";
import Link from "next/link";

export interface SubcontratacaoSetorBlockProps {
  setor: string;
  setorLabel: string;
}

interface SubcontratacaoSetorData {
  percentual_subcontratacao: number;
  total_fornecedores: number;
}

function SubcontratacaoSetorBlock({
  setor,
  setorLabel,
}: SubcontratacaoSetorBlockProps) {
  const [data, setData] = useState<SubcontratacaoSetorData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/pseo/subcontratacao-setor?setor=${encodeURIComponent(setor)}`, {
      signal: controller.signal,
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((json: SubcontratacaoSetorData | null) => setData(json))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [setor]);

  const subText = data
    ? `${data.percentual_subcontratacao}% das empresas vencedoras em ${setorLabel} subcontratam`
    : `Empresas vencedoras em ${setorLabel} frequentemente subcontratam partes de seus contratos p&uacute;blicos`;

  if (!loading && data && data.percentual_subcontratacao === 0) {
    return null;
  }

  return (
    <section
      data-testid="subcontratacao-setor-block"
      className="rounded-xl border border-blue-200 bg-blue-50 dark:bg-blue-950/30 dark:border-blue-800 p-5 my-8"
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl" aria-hidden="true">&#x1F4CA;</span>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-1">
            Subcontrata&ccedil;&atilde;o no setor
          </h3>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
            {loading
              ? "Verificando dados de subcontrata&ccedil;&atilde;o..."
              : subText}
          </p>
          <Link
            href={`/subcontratacao?setor=${encodeURIComponent(setor)}`}
            className="inline-block rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
            data-testid="subcontratacao-setor-cta"
          >
            Ver pontes de subcontrata&ccedil;&atilde;o em {setorLabel} &rarr;
          </Link>
        </div>
      </div>
    </section>
  );
}

export { SubcontratacaoSetorBlock };
export default SubcontratacaoSetorBlock;

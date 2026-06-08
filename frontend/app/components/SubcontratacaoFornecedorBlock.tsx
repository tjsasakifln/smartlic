"use client";
/**
 * SubcontratacaoFornecedorBlock — Issue #1321
 *
 * Block for /fornecedores/[cnpj]:
 * "Este fornecedor venceu X contratos que podem envolver subcontratação"
 * CTA: link to /subcontratacao flagship page.
 *
 * Tenta buscar dados de um endpoint público; se indisponível, mostra
 * placeholder estático com CTA.
 */

import { useEffect, useState } from "react";
import Link from "next/link";

export interface SubcontratacaoFornecedorBlockProps {
  cnpj: string;
  razaoSocial: string;
}

interface SubcontratacaoData {
  contratos_subcontratacao: number;
  total_contratos: number;
}

function SubcontratacaoFornecedorBlock({
  cnpj,
  razaoSocial,
}: SubcontratacaoFornecedorBlockProps) {
  const [data, setData] = useState<SubcontratacaoData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/pseo/subcontratacao-fornecedor?cnpj=${encodeURIComponent(cnpj)}`, {
      signal: controller.signal,
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((json: SubcontratacaoData | null) => setData(json))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, [cnpj]);

  const contratosText = data
    ? `Este fornecedor venceu ${data.contratos_subcontratacao} contratos que podem envolver subcontratação`
    : `Fornecedores como ${razaoSocial} frequentemente subcontratam partes de seus contratos públicos`;

  if (!loading && data && data.contratos_subcontratacao === 0) {
    return null;
  }

  return (
    <section
      data-testid="subcontratacao-fornecedor-block"
      className="rounded-xl border border-blue-200 bg-blue-50 dark:bg-blue-950/30 dark:border-blue-800 p-5 my-8"
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl" aria-hidden="true">&#x1F517;</span>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-1">
            Pontes de subcontrata&ccedil;&atilde;o
          </h3>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
            {loading
              ? "Verificando oportunidades de subcontrata&ccedil;&atilde;o..."
              : contratosText}
          </p>
          <Link
            href="/subcontratacao"
            className="inline-block rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
            data-testid="subcontratacao-fornecedor-cta"
          >
            Ver pontes de subcontrata&ccedil;&atilde;o &rarr;
          </Link>
        </div>
      </div>
    </section>
  );
}

export { SubcontratacaoFornecedorBlock };
export default SubcontratacaoFornecedorBlock;

"use client";
/**
 * SubcontratacaoOrgaoBlock — Issue #1321
 *
 * Block for /orgaos/[slug]:
 * "Fornecedores recorrentes deste órgão que podem subcontratar"
 * CTA: link to /subcontratacao flagship page.
 */

import Link from "next/link";

export interface SubcontratacaoOrgaoBlockProps {
  slug: string;
  nome: string;
}

function SubcontratacaoOrgaoBlock({
  slug,
  nome,
}: SubcontratacaoOrgaoBlockProps) {
  return (
    <section
      data-testid="subcontratacao-orgao-block"
      className="rounded-xl border border-blue-200 bg-blue-50 dark:bg-blue-950/30 dark:border-blue-800 p-5 my-8"
    >
      <div className="flex items-start gap-3">
        <span className="text-2xl" aria-hidden="true">&#x1F50D;</span>
        <div className="flex-1 min-w-0">
          <h3 className="text-sm font-semibold text-slate-900 dark:text-white mb-1">
            Subcontrata&ccedil;&atilde;o
          </h3>
          <p className="text-sm text-slate-600 dark:text-slate-400 mb-3">
            Fornecedores recorrentes de {nome} que podem subcontratar partes
            de seus contratos p&uacute;blicos. Identifique pontes para novos neg&oacute;cios.
          </p>
          <Link
            href="/subcontratacao"
            className="inline-block rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 transition-colors"
            data-testid="subcontratacao-orgao-cta"
          >
            Mapear pontes neste &oacute;rg&atilde;o &rarr;
          </Link>
        </div>
      </div>
    </section>
  );
}

export { SubcontratacaoOrgaoBlock };
export default SubcontratacaoOrgaoBlock;

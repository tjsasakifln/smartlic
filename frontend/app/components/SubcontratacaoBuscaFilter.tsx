"use client";
/**
 * SubcontratacaoBuscaFilter — Issue #1321
 *
 * Filter toggle for /buscar sidebar:
 * "Oportunidades de subcontratação"
 * Simple toggle component that emits onChange.
 */

export interface SubcontratacaoBuscaFilterProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  disabled?: boolean;
}

function SubcontratacaoBuscaFilter({
  checked,
  onChange,
  disabled = false,
}: SubcontratacaoBuscaFilterProps) {
  return (
    <label
      data-testid="subcontratacao-busca-filter"
      className="flex items-center justify-between gap-3 py-3 px-4 rounded-lg bg-surface-1 border border-strong cursor-pointer hover:bg-brand-blue-subtle transition-colors"
    >
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-lg" aria-hidden="true">&#x1F517;</span>
        <span className="text-sm font-medium text-ink">
          Oportunidades de subcontrata&ccedil;&atilde;o
        </span>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        disabled={disabled}
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-blue focus-visible:ring-offset-2 ${
          checked ? "bg-brand-blue" : "bg-gray-200 dark:bg-gray-700"
        } ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
      >
        <span
          aria-hidden="true"
          className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
            checked ? "translate-x-4" : "translate-x-0"
          }`}
        />
      </button>
    </label>
  );
}

export { SubcontratacaoBuscaFilter };
export default SubcontratacaoBuscaFilter;

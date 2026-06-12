'use client';

import { useState, useCallback } from 'react';

interface CompetitorSearchProps {
  onSearch: (cnpj: string) => void;
  loading: boolean;
}

const CNPJ_MASK = 'XX.XXX.XXX/XXXX-XX';

function formatCNPJ(value: string): string {
  const digits = value.replace(/\D/g, '').slice(0, 14);
  if (digits.length <= 2) return digits;
  if (digits.length <= 5) return `${digits.slice(0, 2)}.${digits.slice(2)}`;
  if (digits.length <= 8)
    return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5)}`;
  if (digits.length <= 12)
    return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8)}`;
  return `${digits.slice(0, 2)}.${digits.slice(2, 5)}.${digits.slice(5, 8)}/${digits.slice(8, 12)}-${digits.slice(12)}`;
}

export default function CompetitorSearch({ onSearch, loading }: CompetitorSearchProps) {
  const [cnpj, setCnpj] = useState('');

  const handleChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setCnpj(formatCNPJ(e.target.value));
    },
    []
  );

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const raw = cnpj.replace(/\D/g, '');
      if (raw.length === 14) {
        onSearch(raw);
      }
    },
    [cnpj, onSearch]
  );

  const isValid = cnpj.replace(/\D/g, '').length === 14;

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg bg-white p-4 shadow-sm"
    >
      <label
        htmlFor="cnpj-search"
        className="block text-sm font-medium text-gray-700"
      >
        Buscar Concorrente por CNPJ
      </label>
      <div className="mt-1 flex gap-2">
        <input
          id="cnpj-search"
          type="text"
          value={cnpj}
          onChange={handleChange}
          placeholder={CNPJ_MASK}
          maxLength={18}
          className="block w-full max-w-xs rounded-md border border-gray-300 px-3 py-2 shadow-sm focus:border-blue-500 focus:outline-none focus:ring-blue-500 sm:text-sm"
          autoComplete="off"
        />
        <button
          type="submit"
          disabled={!isValid || loading}
          className="inline-flex items-center rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? 'Buscando...' : 'Analisar'}
        </button>
      </div>
      <p className="mt-1 text-xs text-gray-500">
        Digite o CNPJ com 14 digitos (a mascara e aplicada automaticamente)
      </p>
    </form>
  );
}

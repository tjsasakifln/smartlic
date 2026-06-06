'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useUser } from '../../../contexts/UserContext';

/**
 * API-SELF-006 (#1425): Dashboard de uso da API na /conta/api.
 *
 * Mostra:
 * - Status das API keys (ativa, nunca usada, sem key)
 * - Consumo do mês atual vs limite do plano
 * - Gráfico de uso diário (Recharts)
 * - Botão de upgrade para tier superior
 */

interface ApiKeyInfo {
  id: string;
  name: string;
  created_at: string;
  last_used_at: string | null;
  revoked_at: string | null;
}

interface DailyUsage {
  date: string;
  count: number;
}

interface ApiUsageData {
  api_keys: ApiKeyInfo[];
  current_month_usage: number;
  monthly_limit: number;
  tier: string;
  daily_usage: DailyUsage[];
  month: string;
}

const TIER_LABELS: Record<string, string> = {
  starter: 'Starter',
  pro: 'Pro',
  scale: 'Scale',
  unlimited: 'Ilimitado',
  none: 'Sem plano',
};

const TIER_UPGRADE: Record<string, { tier: string; label: string; price: string } | null> = {
  none: { tier: 'api_starter', label: 'Starter', price: 'R$97/mês' },
  starter: { tier: 'api_pro', label: 'Pro', price: 'R$297/mês' },
  pro: { tier: 'api_scale', label: 'Scale', price: 'R$970/mês' },
  scale: null,
  unlimited: null,
};

export default function ApiUsagePage() {
  const { user, session, authLoading } = useUser();
  const [data, setData] = useState<ApiUsageData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchUsage = useCallback(async () => {
    if (!session?.access_token) return;
    setLoading(true);
    setError(null);
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://api.smartlic.tech';
      const res = await fetch(`${apiUrl}/v1/conta/api-usage`, {
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
      });
      if (!res.ok) {
        throw new Error(`Erro ${res.status}: ${res.statusText}`);
      }
      const json: ApiUsageData = await res.json();
      setData(json);
    } catch (err: any) {
      setError(err.message || 'Erro ao carregar dados de uso da API.');
    } finally {
      setLoading(false);
    }
  }, [session?.access_token]);

  useEffect(() => {
    if (session?.access_token) {
      fetchUsage();
    }
  }, [session?.access_token, fetchUsage]);

  if (authLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-[var(--ink-secondary)]">Carregando...</p>
      </div>
    );
  }

  if (!user || !session) {
    return (
      <div className="text-center py-12">
        <p className="text-[var(--ink-secondary)] mb-4">
          Faça login para acessar sua conta
        </p>
        <Link
          href="/login"
          className="text-[var(--brand-blue)] hover:underline"
        >
          Ir para login
        </Link>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="space-y-6 animate-pulse">
        <div className="h-10 w-48 bg-[var(--surface-1)] rounded" />
        <div className="h-48 bg-[var(--surface-1)] rounded-card" />
        <div className="h-64 bg-[var(--surface-1)] rounded-card" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-12">
        <p className="text-[var(--ink-secondary)] mb-4">
          {error || 'Dados indisponíveis.'}
        </p>
        <button
          onClick={fetchUsage}
          className="px-4 py-2 rounded-button bg-[var(--brand-navy)] text-white text-sm font-medium hover:bg-[var(--brand-blue)] transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  const { api_keys, current_month_usage, monthly_limit, tier, daily_usage, month } = data;
  const usagePct = monthly_limit > 0
    ? Math.min(Math.round((current_month_usage / monthly_limit) * 100), 100)
    : 0;
  const hasActiveKey = api_keys.some((k) => !k.revoked_at);
  const upgrade = TIER_UPGRADE[tier] || null;
  const tierLabel = TIER_LABELS[tier] || tier;
  const isUnlimited = tier === 'unlimited';

  // Format the month for display
  const [year, monthNum] = month.split('-');
  const monthName = new Date(parseInt(year), parseInt(monthNum) - 1).toLocaleString('pt-BR', { month: 'long', year: 'numeric' });

  // Chart tooltip
  const chartData = daily_usage.map((d) => ({
    ...d,
    displayDate: d.date.slice(-2), // Just the day
  }));

  return (
    <div className="space-y-6" data-testid="api-usage-page">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h1 className="text-xl font-bold text-[var(--ink)] font-display">API</h1>
        <div className="flex items-center gap-2">
          <Link
            href="/api"
            target="_blank"
            className="text-xs text-[var(--brand-blue)] hover:underline"
          >
            Documentação da API →
          </Link>
        </div>
      </div>

      {/* Tier & Usage Overview */}
      <div className="p-6 bg-[var(--surface-0)] border border-[var(--border)] rounded-card" data-testid="api-tier-section">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-lg font-semibold text-[var(--ink)]">
              Plano {tierLabel}
            </h2>
            {!isUnlimited && (
              <p className="text-sm text-[var(--ink-secondary)]">
                {current_month_usage.toLocaleString('pt-BR')} de{' '}
                {monthly_limit.toLocaleString('pt-BR')} requisições em {monthName}
              </p>
            )}
            {isUnlimited && (
              <p className="text-sm text-[var(--ink-secondary)]">
                {current_month_usage.toLocaleString('pt-BR')} requisições em {monthName}
              </p>
            )}
          </div>
          {upgrade && (
            <Link
              href={`/checkout?plan=${upgrade.tier}`}
              className="px-3 py-1.5 rounded-button bg-[var(--brand-navy)] text-white text-xs font-medium hover:bg-[var(--brand-blue)] transition-colors"
            >
              Upgrade para {upgrade.label}
            </Link>
          )}
        </div>

        {/* Usage bar */}
        {!isUnlimited && (
          <div className="space-y-2">
            <div className="w-full h-3 bg-[var(--surface-1)] rounded-full overflow-hidden">
              {/* eslint-disable-next-line local-rules/no-inline-styles */}
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${usagePct}%`,
                  backgroundColor:
                    usagePct > 80 ? 'var(--error)' : 'var(--brand-blue)',
                }}
              />
            </div>
            <p className="text-xs text-[var(--ink-muted)] text-right">
              {usagePct}% utilizado
            </p>
          </div>
        )}
      </div>

      {/* Daily Usage Chart */}
      {daily_usage.length > 0 && (
        <div className="p-6 bg-[var(--surface-0)] border border-[var(--border)] rounded-card" data-testid="api-usage-chart">
          <h3 className="text-sm font-semibold text-[var(--ink)] mb-4">
            Consumo Diário — {monthName}
          </h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis
                  dataKey="displayDate"
                  tick={{ fontSize: 11, fill: 'var(--ink-muted)' }}
                  axisLine={{ stroke: 'var(--border)' }}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fontSize: 11, fill: 'var(--ink-muted)' }}
                  axisLine={{ stroke: 'var(--border)' }}
                  tickLine={false}
                  width={45}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: 'var(--surface-0)',
                    border: '1px solid var(--border)',
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  labelFormatter={(label) => `${label}/${monthNum}/${year}`}
                  formatter={((value: number) => [`${value} req`, 'Requisições']) as any}
                />
                <ReferenceLine
                  y={monthly_limit / 30}
                  stroke="var(--warning)"
                  strokeDasharray="5 5"
                  strokeWidth={1}
                  label={{
                    value: 'Média diária',
                    position: 'insideTopRight',
                    fill: 'var(--warning)',
                    fontSize: 10,
                  }}
                />
                <Bar
                  dataKey="count"
                  fill="var(--brand-blue)"
                  radius={[4, 4, 0, 0]}
                  maxBarSize={32}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* API Keys */}
      <div className="p-6 bg-[var(--surface-0)] border border-[var(--border)] rounded-card" data-testid="api-keys-section">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-[var(--ink)]">
            Suas Chaves de API
          </h3>
          <Link
            href="/conta/seguranca"
            className="text-xs text-[var(--brand-blue)] hover:underline"
          >
            Gerenciar chaves
          </Link>
        </div>

        {api_keys.length === 0 ? (
          <div className="text-center py-8">
            <div className="w-12 h-12 rounded-full bg-[var(--surface-1)] flex items-center justify-center mx-auto mb-3">
              <svg className="w-6 h-6 text-[var(--ink-muted)]" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z" />
              </svg>
            </div>
            <p className="text-sm text-[var(--ink-secondary)] mb-3">
              Você ainda não tem chaves de API.
            </p>
            <Link
              href="/conta/seguranca"
              className="inline-flex px-4 py-2 rounded-button bg-[var(--brand-navy)] text-white text-sm font-medium hover:bg-[var(--brand-blue)] transition-colors"
            >
              Criar Chave de API
            </Link>
          </div>
        ) : (
          <div className="space-y-3">
            {api_keys.map((key) => (
              <div
                key={key.id}
                className="flex items-center justify-between p-3 bg-[var(--surface-1)] rounded-input"
                data-testid={`api-key-${key.id.slice(0, 8)}`}
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-[var(--ink)] truncate">
                    {key.name || 'Chave sem nome'}
                  </p>
                  <p className="text-xs text-[var(--ink-muted)]">
                    Criada em{' '}
                    {new Date(key.created_at).toLocaleDateString('pt-BR')}
                    {key.last_used_at
                      ? ` · Último uso: ${new Date(key.last_used_at).toLocaleDateString('pt-BR')}`
                      : ' · Nunca usada'}
                  </p>
                </div>
                <div className="flex-shrink-0 ml-3">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                      key.revoked_at
                        ? 'bg-red-100 text-red-700'
                        : 'bg-emerald-100 text-emerald-700'
                    }`}
                  >
                    {key.revoked_at ? 'Revogada' : 'Ativa'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Rate Limits Info */}
      <div className="p-6 bg-[var(--surface-0)] border border-[var(--border)] rounded-card">
        <h3 className="text-sm font-semibold text-[var(--ink)] mb-3">
          Rate Limits
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="text-center p-3 bg-[var(--surface-1)] rounded-input">
            <p className="text-xs text-[var(--ink-muted)] mb-1">Limite Mensal</p>
            <p className="text-lg font-bold text-[var(--ink)]">
              {isUnlimited ? 'Ilimitado' : monthly_limit.toLocaleString('pt-BR')}
            </p>
          </div>
          <div className="text-center p-3 bg-[var(--surface-1)] rounded-input">
            <p className="text-xs text-[var(--ink-muted)] mb-1">Reset</p>
            <p className="text-lg font-bold text-[var(--ink)]">Dia 1º (00:00 BRT)</p>
          </div>
          <div className="text-center p-3 bg-[var(--surface-1)] rounded-input">
            <p className="text-xs text-[var(--ink-muted)] mb-1">Headers</p>
            <p className="text-xs font-mono text-[var(--ink)]">
              X-RateLimit-Limit
              <br />
              X-RateLimit-Remaining
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

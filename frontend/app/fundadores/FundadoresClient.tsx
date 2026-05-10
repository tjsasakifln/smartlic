'use client';

import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { trackFoundersCheckoutAbandoned } from '@/lib/analytics/founders';
import FundadoresForm from './components/FundadoresForm';
import FundadoresFAQ from './components/FundadoresFAQ';
import FundadoresFeatures from './components/FundadoresFeatures';
import FundadoresCountdown, { FoundingAvailabilitySnapshot } from './components/FundadoresCountdown';

function trackEvent(name: string, props?: Record<string, unknown>) {
  if (typeof window === 'undefined') return;
  const mp = (window as unknown as { mixpanel?: { track: (e: string, p?: Record<string, unknown>) => void } }).mixpanel;
  if (!mp) return;
  try {
    mp.track(name, props ?? {});
  } catch {
    // no-op
  }
}

const REFRESH_INTERVAL_MS = 60_000;


// TODO: remove hardcoded fallback after #782 merges (price_brl_cents in API response)
function formatPrice(priceBrlCents: number | undefined): string {
  if (priceBrlCents !== undefined && priceBrlCents > 0) {
    return (priceBrlCents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  }
  return 'R$997';
}

export default function FundadoresClient() {
  const [snapshot, setSnapshot] = useState<FoundingAvailabilitySnapshot | null>(null);
  const searchParams = useSearchParams();
  const abandonedTrackedRef = useRef(false);

  useEffect(() => {
    trackEvent('fundadores_page_viewed', { source: 'landing' });
  }, []);

  // Track checkout abandoned when user returns from Stripe with ?cancelled=true
  useEffect(() => {
    if (!abandonedTrackedRef.current && searchParams?.get('cancelled') === 'true') {
      abandonedTrackedRef.current = true;
      trackFoundersCheckoutAbandoned({ src: searchParams?.get('src') });
    }
  }, [searchParams]);

  useEffect(() => {
    let cancelled = false;
    let timer: ReturnType<typeof setInterval> | null = null;

    async function load() {
      try {
        const res = await fetch('/api/founding/availability', { cache: 'no-store' });
        if (!res.ok) {
          if (!cancelled) {
            setSnapshot({
              available: false,
              seats_total: 50,
              seats_remaining: 0,
              seats_taken: 50,
              deadline_at: null,
              paused: false,
              reason: 'unavailable',
              coupon_code: 'FOUNDING_LIFETIME',
              discount_pct: 0,
            });
          }
          return;
        }
        const data = (await res.json()) as FoundingAvailabilitySnapshot;
        if (!cancelled) setSnapshot(data);
      } catch {
        if (!cancelled) {
          setSnapshot({
            available: false,
            seats_total: 50,
            seats_remaining: 0,
            seats_taken: 50,
            deadline_at: null,
            paused: false,
            reason: 'unavailable',
            coupon_code: 'FOUNDING_LIFETIME',
            discount_pct: 0,
          });
        }
      }
    }

    load();
    timer = setInterval(load, REFRESH_INTERVAL_MS);
    return () => {
      cancelled = true;
      if (timer) clearInterval(timer);
    };
  }, []);

  const price = formatPrice(snapshot?.price_brl_cents);
  const seatsRemaining = snapshot?.seats_remaining ?? null;
  const seatsRemainingText = seatsRemaining !== null ? `${seatsRemaining}` : '50';

  return (
    <main className="min-h-screen bg-white">
      {/* Hero — founder pact framing */}
      <section className="bg-slate-900 text-white">
        <div className="mx-auto max-w-3xl px-4 py-16">
          <p className="text-sm uppercase tracking-widest text-blue-400 font-semibold mb-3">
            Plano Fundadores · 50 vagas · Encerra 30/06/2026
          </p>
          <h1 className="text-3xl sm:text-5xl font-bold leading-tight mb-4">
            Pague {price} uma vez. Use o SmartLic pra sempre.
          </h1>
          <p className="text-lg sm:text-xl text-slate-300 mb-8">
            50 empresas. {price} pagamento único. Acesso vitalício a tudo que existe e tudo
            que vier. Sem mensalidade. Encerra 30 de junho de 2026 — ou quando as 50 vagas
            acabarem (faltam {seatsRemainingText}).
          </p>

          <div className="mb-8">
            <FundadoresCountdown snapshot={snapshot} />
          </div>

          <div className="rounded-xl border border-blue-500/30 bg-blue-950/40 p-6">
            <p className="text-2xl font-bold text-white mb-1">
              {price} <span className="text-base font-normal text-slate-400">pagamento único</span>
            </p>
            <p className="text-slate-300 text-sm mb-4">
              Pagamento único no Pix ou cartão. 60 dias de garantia incondicional.
            </p>
            <FundadoresForm availability={snapshot} price={price} />
            <p className="mt-3 text-xs text-slate-400">
              Prefere testar antes?{' '}
              <a href="/planos" className="text-blue-300 underline hover:text-blue-200">
                Comece com 14 dias grátis →
              </a>
            </p>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-3xl px-4 py-12">
        {/* Carta do founder */}
        <section aria-labelledby="carta-heading" className="mb-16">
          <h2 id="carta-heading" className="text-2xl font-semibold text-slate-900 mb-6">
            Uma carta de quem fez isso
          </h2>
          <div className="flex items-start gap-4 mb-6">
            <div
              aria-hidden="true"
              className="h-16 w-16 rounded-full bg-slate-200 flex items-center justify-center text-slate-500 font-semibold flex-shrink-0"
            >
              TS
            </div>
            <div>
              <p className="font-semibold text-slate-900">Tiago Sasaki</p>
              <p className="text-sm text-slate-600">Fundador, SmartLic · CONFENGE Avaliações e IA</p>
              <p className="text-sm text-slate-600 mt-1">
                <a
                  href="https://www.linkedin.com/in/tiagosasaki/"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-blue-600 underline"
                >
                  LinkedIn
                </a>
                {' · '}
                <a href="mailto:tiago@smartlic.tech" className="text-blue-600 underline">
                  tiago@smartlic.tech
                </a>
              </p>
            </div>
          </div>
          <div className="prose prose-slate max-w-none text-slate-700 leading-relaxed">
            <p>Olá. Sou o Tiago.</p>
            <p className="mt-4">
              Sou engenheiro civil. Passei 10 anos como servidor público no setor de obras
              de uma prefeitura. Desse outro lado do balcão, vi duas coisas todo dia:
            </p>
            <p className="mt-4">
              <strong>Primeiro:</strong> empresas pequenas e médias perdendo licitações
              boas porque não viram o edital a tempo. Edital publicado terça à tarde,
              prazo curto, abertura na sexta. Quem tinha equipe pra varrer PNCP toda hora
              entrava. Quem não tinha, ficava de fora — não por incompetência, por falta
              de informação no momento certo.
            </p>
            <p className="mt-4">
              <strong>Segundo:</strong> consultoria de licitação cobrando
              R$3.000–R$8.000/mês para fazer triagem manual que uma IA bem feita resolve.
              Empresário B2G pagando salário de gente para ler PDF.
            </p>
            <p className="mt-4">
              Saí em 2025 e construí o SmartLic com a CONFENGE. Hoje a plataforma indexa{' '}
              <strong>2.187.430 contratos públicos</strong>, monitora{' '}
              <strong>27 UFs em tempo real</strong>, classifica em{' '}
              <strong>20 setores</strong> com IA, e está em produção (Railway + Supabase,
              não é demo).
            </p>
            <p className="mt-4">
              Eu poderia esperar mais 6 meses, dar polimento, lançar com pricing tradicional
              R$397/mês, e tentar bootstrappar do zero. Não vou fazer isso.
            </p>
            <p className="mt-4">
              Estou abrindo <strong>50 vagas</strong> de acesso vitalício por R$997
              one-time. Em troca de quê? De runway honesto pros próximos 6 meses (50 ×
              R$997 = R$49.850, dá pra terminar o roadmap sem captar) e de 50 parceiros
              que vão usar de verdade, reclamar quando algo quebrar, e me dizer o que falta.
            </p>
            <p className="mt-4">
              Não é &quot;early bird&quot; de marketing. É um pacto: você banca a próxima
              fase, eu garanto que você nunca mais paga mensalidade — independentemente do
              que aconteça com o pricing depois.
            </p>
            <p className="mt-4">
              Se faz sentido pra você, está aí em cima.
            </p>
            <p className="mt-4">— Tiago</p>
          </div>
        </section>

        {/* A conta do uma vez vs todo mês */}
        <section aria-labelledby="conta-heading" className="mb-16">
          <h2 id="conta-heading" className="text-2xl font-semibold text-slate-900 mb-2">
            A conta do uma vez vs todo mês
          </h2>
          <p className="text-slate-600 mb-6">
            Pro mensal regular custa R$397/mês. Veja o que isso vira ao longo do tempo
            comparado ao pagamento único de fundador.
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr className="bg-slate-100">
                  <th className="text-left px-4 py-3 font-semibold text-slate-700 border border-slate-200">
                    Período
                  </th>
                  <th className="text-center px-4 py-3 font-semibold text-slate-700 border border-slate-200">
                    Pro mensal (R$397/mês)
                  </th>
                  <th className="text-center px-4 py-3 font-semibold text-blue-700 border border-slate-200">
                    Fundador (R$997 único)
                  </th>
                  <th className="text-center px-4 py-3 font-semibold text-emerald-700 border border-slate-200">
                    Você economiza
                  </th>
                </tr>
              </thead>
              <tbody>
                {[
                  { periodo: '12 meses (1 ano)', mensal: 4764, economia: 4764 - 997 },
                  { periodo: '24 meses (2 anos)', mensal: 9528, economia: 9528 - 997 },
                  { periodo: '60 meses (5 anos)', mensal: 23820, economia: 23820 - 997 },
                ].map((row) => (
                  <tr key={row.periodo} className="border border-slate-200 hover:bg-slate-50">
                    <td className="px-4 py-3 text-slate-700 border border-slate-200 font-medium">
                      {row.periodo}
                    </td>
                    <td className="px-4 py-3 text-center text-slate-600 border border-slate-200">
                      R${row.mensal.toLocaleString('pt-BR')}
                    </td>
                    <td className="px-4 py-3 text-center font-medium text-blue-700 border border-slate-200">
                      R$997
                    </td>
                    <td className="px-4 py-3 text-center font-semibold text-emerald-700 border border-slate-200">
                      R${row.economia.toLocaleString('pt-BR')}
                    </td>
                  </tr>
                ))}
                <tr className="bg-emerald-50 border border-slate-200">
                  <td
                    colSpan={4}
                    className="px-4 py-3 text-center text-emerald-800 border border-slate-200 font-semibold"
                  >
                    Em 5 anos, fundadores economizam mais de R$22 mil — e seguem com acesso
                    pra sempre.
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        {/* O que está incluído (9 bullets) */}
        <FundadoresFeatures />

        {/* As 4 perguntas que todo mundo me faz */}
        <FundadoresFAQ />

        {/* Quem não deveria comprar */}
        <section
          aria-labelledby="nao-deveria-heading"
          className="mt-16 rounded-xl border border-amber-200 bg-amber-50 p-6"
        >
          <h2 id="nao-deveria-heading" className="text-2xl font-semibold text-slate-900 mb-2">
            Quem não deveria comprar
          </h2>
          <p className="text-slate-700 mb-4">
            Honestidade vale mais do que conversão. Se você se encaixa em um destes três
            perfis, não compre — vai ficar frustrado e eu vou ter que devolver na garantia
            de 60 dias.
          </p>
          <ul className="space-y-3 text-slate-700">
            <li className="flex gap-3">
              <span aria-hidden="true" className="text-amber-700 font-bold">×</span>
              <span>
                <strong>Empresa com faturamento abaixo de R$200 mil/ano.</strong>{' '}
                Licitação pública exige capital de giro, fluxo de caixa, capacidade
                operacional. R$997 não vai te tornar elegível se a estrutura financeira
                não está pronta. Cresça primeiro, automatize depois.
              </span>
            </li>
            <li className="flex gap-3">
              <span aria-hidden="true" className="text-amber-700 font-bold">×</span>
              <span>
                <strong>Empresa sem CRC ou habilitação técnica do setor.</strong>{' '}
                O SmartLic encontra e qualifica editais — mas não emite atestado,
                não substitui registro profissional, não resolve falta de habilitação.
                Resolva o cadastro antes; o software vem depois.
              </span>
            </li>
            <li className="flex gap-3">
              <span aria-hidden="true" className="text-amber-700 font-bold">×</span>
              <span>
                <strong>Quem espera &quot;garantia de ganhar licitação&quot;.</strong>{' '}
                Não existe. Quem te promete isso está mentindo ou cobrando ilegalmente.
                O SmartLic aumenta a probabilidade de encontrar editais bons no momento
                certo — quem ganha é a sua proposta.
              </span>
            </li>
          </ul>
        </section>

        {/* Garantia 60 dias */}
        <section
          aria-labelledby="garantia-heading"
          className="mt-16 rounded-xl border-2 border-emerald-300 bg-emerald-50 p-6"
        >
          <div className="flex items-start gap-4">
            <div
              aria-hidden="true"
              className="h-16 w-16 rounded-full bg-emerald-600 text-white flex items-center justify-center font-bold text-lg flex-shrink-0"
            >
              60d
            </div>
            <div>
              <h2 id="garantia-heading" className="text-2xl font-semibold text-slate-900 mb-2">
                Garantia incondicional de 60 dias
              </h2>
              <p className="text-slate-700 leading-relaxed mb-3">
                Use o SmartLic por 60 dias. Se em qualquer momento dos primeiros dois meses
                você decidir que não vale, devolvo 100% do valor pago. Sem perguntas, sem
                formulário longo, sem &quot;tem certeza?&quot; três vezes.
              </p>
              <p className="text-slate-700 leading-relaxed mb-2">
                <strong>Como pedir reembolso:</strong>
              </p>
              <ol className="list-decimal pl-5 space-y-1 text-slate-700 mb-3">
                <li>
                  Envie um email para{' '}
                  <a
                    href="mailto:tiago@smartlic.tech?subject=reembolso"
                    className="text-blue-700 underline font-medium"
                  >
                    tiago@smartlic.tech
                  </a>{' '}
                  com assunto <code className="bg-white px-1.5 py-0.5 rounded border border-slate-200">reembolso</code>.
                </li>
                <li>Não preciso saber por quê. Reembolso processado em até 5 dias úteis.</li>
                <li>Acesso à plataforma é encerrado após o reembolso confirmar.</li>
              </ol>
              <p className="text-sm text-slate-600">
                Vale para qualquer um dos primeiros 60 dias após o pagamento confirmado.
                Eu assino embaixo.
              </p>
            </div>
          </div>
        </section>

        {/* Vagas em tempo real */}
        <section
          aria-labelledby="vagas-heading"
          className="mt-16 rounded-lg border border-slate-200 bg-slate-50 p-6"
        >
          <h2 id="vagas-heading" className="text-xl font-semibold text-slate-900 mb-3">
            Vagas em tempo real
          </h2>
          <p className="text-slate-700">
            <strong className="text-blue-700 text-2xl">{seatsRemainingText}</strong>{' '}
            <span className="text-slate-600">de 50 vagas restantes.</span>
          </p>
          <p className="text-sm text-slate-500 mt-2">
            Contador atualiza a cada minuto direto do banco — não é counter de marketing.
            Quando zerar, encerra antes de 30/06/2026.
          </p>
        </section>

        {/* CTA final */}
        <section
          aria-labelledby="cta-final-heading"
          className="mt-16 rounded-xl border border-blue-200 bg-blue-50 p-8"
        >
          <h2 id="cta-final-heading" className="text-2xl font-semibold text-slate-900 mb-2">
            Quero uma das {seatsRemainingText} vagas — {price}
          </h2>
          <p className="text-slate-700 mb-6">
            Pagamento único no Pix ou cartão. 60 dias de garantia incondicional. Acesso
            ativado na hora.
          </p>
          <FundadoresForm availability={snapshot} price={price} />
          <p className="mt-4 text-sm text-slate-600">
            Prefere testar antes?{' '}
            <a href="/planos" className="text-blue-700 underline hover:text-blue-800 font-medium">
              Comece com 14 dias grátis →
            </a>
          </p>
        </section>

        {/* Disclaimer legal */}
        <footer className="mt-12 border-t border-slate-200 pt-6 text-sm text-slate-500">
          <p>
            Ao prosseguir, você concorda com os{' '}
            <a href="/termos/fundadores" className="text-blue-600 underline">
              Termos do Plano Fundadores
            </a>{' '}
            e a{' '}
            <a href="/privacidade" className="text-blue-600 underline">
              Política de Privacidade
            </a>
            . Em caso de dúvida, escreva para{' '}
            <a href="mailto:tiago@smartlic.tech" className="text-blue-600 underline">
              tiago@smartlic.tech
            </a>
            .
          </p>
        </footer>
      </div>
    </main>
  );
}

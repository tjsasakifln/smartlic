"use client";

/**
 * ABTestWidget — A/B test results dashboard for admin.
 *
 * Placeholder: displays active experiments and conversion stats.
 * Full implementation pending A/B testing infrastructure.
 */
export function ABTestWidget() {
  return (
    <section className="rounded-card border bg-[var(--surface-0)] p-6">
      <h2 className="text-lg font-semibold mb-4">Testes A/B Ativos</h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        <ExperimentCard
          name="Ordenação Padrão"
          variant="confianca (v2)"
          control="data_desc (v1)"
          conversion="+12.4%"
          status="running"
        />
      </div>
      <p className="text-xs text-[var(--text-secondary)] mt-4">
        Infraestrutura de testes A/B em implantação. Dados preliminares.
      </p>
    </section>
  );
}

function ExperimentCard({
  name,
  variant,
  control,
  conversion,
  status,
}: {
  name: string;
  variant: string;
  control: string;
  conversion: string;
  status: string;
}) {
  const statusColors: Record<string, string> = {
    running: "bg-green-100 text-green-800",
    paused: "bg-yellow-100 text-yellow-800",
    completed: "bg-blue-100 text-blue-800",
  };

  return (
    <div className="border rounded-card p-4 space-y-2">
      <div className="flex items-center justify-between">
        <span className="font-medium text-sm">{name}</span>
        <span
          className={`text-xs px-2 py-0.5 rounded-full ${statusColors[status] ?? "bg-gray-100 text-gray-800"}`}
        >
          {status}
        </span>
      </div>
      <div className="text-xs space-y-1">
        <div className="flex justify-between">
          <span className="text-[var(--text-secondary)]">Variante</span>
          <span className="font-medium">{variant}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[var(--text-secondary)]">Controle</span>
          <span>{control}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-[var(--text-secondary)]">Conversão</span>
          <span className="font-medium text-green-600">{conversion}</span>
        </div>
      </div>
    </div>
  );
}

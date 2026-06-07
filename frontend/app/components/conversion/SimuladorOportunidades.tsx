"use client";

import { useState, useCallback, useMemo } from "react";
import Link from "next/link";
import { CustomSelect, type SelectOption } from "../CustomSelect";
import { formatCurrencyBR } from "@/lib/format-currency";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SimulatedOpportunity {
  id: number;
  orgao: string;
  objeto: string;
  valor: number;
  modalidade: string;
  data_abertura: string;
  data_encerramento: string;
  uf: string;
}

interface SimulatorResult {
  totalCount: number;
  totalValue: number;
  opportunities: SimulatedOpportunity[];
}

export interface SimuladorOportunidadesProps {
  /** Current page path for tracking source_page */
  sourcePage?: string;
  /** Default sector ID to pre-select */
  defaultSector?: string;
  /** Default UF to pre-select */
  defaultUf?: string;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const SECTORS: SelectOption[] = [
  { value: "alimentos", label: "Alimentos e Merenda" },
  { value: "engenharia", label: "Engenharia, Projetos e Obras" },
  { value: "engenharia_rodoviaria", label: "Engenharia Rodoviária e Infraestrutura Viária" },
  { value: "equipamentos_medicos", label: "Equipamentos Médico-Hospitalares" },
  { value: "frota", label: "Frota e Veículos" },
  { value: "hardware", label: "Hardware e Equipamentos de TI" },
  { value: "insumos_hospitalares", label: "Insumos e Materiais Hospitalares" },
  { value: "licenciamento_software", label: "Licenciamento de Software Comercial" },
  { value: "limpeza", label: "Produtos de Limpeza e Higienização" },
  { value: "manutencao_predial", label: "Manutenção e Conservação Predial" },
  { value: "materiais_eletricos", label: "Materiais Elétricos e Instalações" },
  { value: "materiais_hidraulicos", label: "Materiais Hidráulicos e Saneamento" },
  { value: "medicamentos", label: "Medicamentos e Produtos Farmacêuticos" },
  { value: "mobiliario", label: "Mobiliário" },
  { value: "papelaria", label: "Papelaria e Material de Escritório" },
  { value: "servicos_prediais", label: "Serviços Prediais e Facilities" },
  { value: "software", label: "Desenvolvimento de Software e Consultoria de TI" },
  { value: "transporte", label: "Transporte de Pessoas e Cargas" },
  { value: "vestuario", label: "Vestuário e Uniformes" },
  { value: "vigilancia", label: "Vigilância e Segurança Patrimonial" },
];

const UFS: SelectOption[] = [
  { value: "AC", label: "Acre (AC)" },
  { value: "AL", label: "Alagoas (AL)" },
  { value: "AP", label: "Amapá (AP)" },
  { value: "AM", label: "Amazonas (AM)" },
  { value: "BA", label: "Bahia (BA)" },
  { value: "CE", label: "Ceará (CE)" },
  { value: "DF", label: "Distrito Federal (DF)" },
  { value: "ES", label: "Espírito Santo (ES)" },
  { value: "GO", label: "Goiás (GO)" },
  { value: "MA", label: "Maranhão (MA)" },
  { value: "MT", label: "Mato Grosso (MT)" },
  { value: "MS", label: "Mato Grosso do Sul (MS)" },
  { value: "MG", label: "Minas Gerais (MG)" },
  { value: "PA", label: "Pará (PA)" },
  { value: "PB", label: "Paraíba (PB)" },
  { value: "PR", label: "Paraná (PR)" },
  { value: "PE", label: "Pernambuco (PE)" },
  { value: "PI", label: "Piauí (PI)" },
  { value: "RJ", label: "Rio de Janeiro (RJ)" },
  { value: "RN", label: "Rio Grande do Norte (RN)" },
  { value: "RS", label: "Rio Grande do Sul (RS)" },
  { value: "RO", label: "Rondônia (RO)" },
  { value: "RR", label: "Roraima (RR)" },
  { value: "SC", label: "Santa Catarina (SC)" },
  { value: "SP", label: "São Paulo (SP)" },
  { value: "SE", label: "Sergipe (SE)" },
  { value: "TO", label: "Tocantins (TO)" },
];

/** UF weight map — relative market size (based on population proxy) */
const UF_WEIGHT: Record<string, number> = {
  AC: 0.08, AL: 0.3, AP: 0.08, AM: 0.35, BA: 1.2, CE: 0.9,
  DF: 0.5, ES: 0.35, GO: 0.6, MA: 0.6, MT: 0.3, MS: 0.25,
  MG: 1.5, PA: 0.7, PB: 0.35, PR: 0.9, PE: 0.8, PI: 0.3,
  RJ: 1.3, RN: 0.3, RS: 1.0, RO: 0.15, RR: 0.06, SC: 0.6,
  SP: 2.5, SE: 0.2, TO: 0.15,
};

const MODALIDADES = [
  "Pregão Eletrônico",
  "Pregão Presencial",
  "Dispensa de Licitação",
  "Concorrência",
  "Tomada de Preços",
  "Concurso",
  "Leilão",
];

// ---------------------------------------------------------------------------
// Simulation profiles per sector
// ---------------------------------------------------------------------------

interface SectorProfile {
  orgaos: string[];
  templates: string[];
  avgValue: number;
  baseCount: number;
}

const SECTOR_PROFILES: Record<string, SectorProfile> = {
  alimentos: {
    orgaos: [
      "Secretaria de Educação",
      "Secretaria de Assistência Social",
      "Prefeitura Municipal",
      "Fundação de Saúde",
      "Secretaria de Administração",
    ],
    templates: [
      "Aquisição de gêneros alimentícios para merenda escolar",
      "Pregão para fornecimento de alimentos perecíveis e não perecíveis",
      "Contratação de empresa para fornecimento de refeições",
      "Aquisição de cestas básicas para programas sociais",
      "Fornecimento de alimentação para unidades de saúde",
    ],
    avgValue: 450_000,
    baseCount: 18,
  },
  engenharia: {
    orgaos: [
      "Secretaria de Obras",
      "Prefeitura Municipal",
      "Departamento de Infraestrutura",
      "Secretaria de Planejamento",
      "Companhia de Habitação",
    ],
    templates: [
      "Contratação de empresa de engenharia para reforma de prédio público",
      "Elaboração de projetos de engenharia para construção civil",
      "Execução de obra de ampliação de unidade escolar",
      "Serviços de engenharia para pavimentação de vias urbanas",
      "Projeto executivo de engenharia para sistema de drenagem",
    ],
    avgValue: 1_800_000,
    baseCount: 12,
  },
  engenharia_rodoviaria: {
    orgaos: [
      "Departamento de Estradas de Rodagem",
      "Secretaria de Infraestrutura",
      "Prefeitura Municipal",
      "Ministério dos Transportes",
      "Superintendência de Obras",
    ],
    templates: [
      "Contratação de serviços de engenharia para pavimentação asfáltica",
      "Recuperação e manutenção de rodovia estadual",
      "Obras de drenagem e terraplanagem em rodovia",
      "Sinalização horizontal e vertical de vias públicas",
      "Construção de ponte e viaduto em rodovia federal",
    ],
    avgValue: 4_500_000,
    baseCount: 6,
  },
  equipamentos_medicos: {
    orgaos: [
      "Secretaria de Saúde",
      "Hospital Municipal",
      "Fundação Hospitalar",
      "Ministério da Saúde",
      "Santa Casa de Misericórdia",
    ],
    templates: [
      "Aquisição de equipamentos médico-hospitalares para UTI",
      "Compra de aparelhos de ultrassom e raio-X",
      "Fornecimento de equipamentos odontológicos",
      "Aquisição de mobiliário e equipamentos para unidade básica de saúde",
      "Compra de equipamentos de diagnóstico por imagem",
    ],
    avgValue: 850_000,
    baseCount: 8,
  },
  frota: {
    orgaos: [
      "Secretaria de Administração",
      "Prefeitura Municipal",
      "Secretaria de Transportes",
      "Polícia Militar",
      "Departamento de Logística",
    ],
    templates: [
      "Aquisição de veículos para renovação de frota municipal",
      "Compra de caminhões e utilitários para serviços públicos",
      "Fornecimento de veículos leves para administração",
      "Aquisição de ambulâncias para serviço de saúde",
      "Locação de veículos para secretarias municipais",
    ],
    avgValue: 1_200_000,
    baseCount: 7,
  },
  hardware: {
    orgaos: [
      "Secretaria de Educação",
      "Secretaria de Administração",
      "Prefeitura Municipal",
      "Tribunal de Justiça",
      "Secretaria de Tecnologia da Informação",
    ],
    templates: [
      "Aquisição de equipamentos de informática e microcomputadores",
      "Compra de notebooks e tablets para administração pública",
      "Fornecimento de servidores e equipamentos de rede",
      "Aquisição de impressoras e scanners",
      "Compra de equipamentos de TI para telecentros",
    ],
    avgValue: 600_000,
    baseCount: 15,
  },
  insumos_hospitalares: {
    orgaos: [
      "Secretaria de Saúde",
      "Hospital Municipal",
      "Fundação de Saúde",
      "Ministério da Saúde",
      "Unidade de Pronto Atendimento",
    ],
    templates: [
      "Aquisição de materiais hospitalares e descartáveis",
      "Fornecimento de insumos para laboratório de análises",
      "Compra de materiais cirúrgicos e de curativo",
      "Aquisição de kits de procedimentos médicos",
      "Fornecimento de materiais de esterilização",
    ],
    avgValue: 400_000,
    baseCount: 14,
  },
  licenciamento_software: {
    orgaos: [
      "Secretaria de Administração",
      "Tribunal de Contas",
      "Prefeitura Municipal",
      "Secretaria de Tecnologia",
      "Procuradoria Geral",
    ],
    templates: [
      "Licenciamento de software de gestão administrativa",
      "Aquisição de licenças de sistema operacional e ferramentas de escritório",
      "Contratação de solução de software para gestão pública",
      "Renovação de licenças de segurança da informação",
      "Licenciamento de plataforma de gestão de processos",
    ],
    avgValue: 350_000,
    baseCount: 6,
  },
  limpeza: {
    orgaos: [
      "Secretaria de Administração",
      "Prefeitura Municipal",
      "Secretaria de Educação",
      "Fundação de Saúde",
      "Departamento de Logística",
    ],
    templates: [
      "Aquisição de materiais de limpeza e higienização",
      "Fornecimento de produtos de limpeza profissional",
      "Compra de materiais de higiene e descartáveis",
      "Aquisição de equipamentos de limpeza",
      "Fornecimento de insumos para serviços de limpeza",
    ],
    avgValue: 250_000,
    baseCount: 16,
  },
  manutencao_predial: {
    orgaos: [
      "Secretaria de Administração",
      "Prefeitura Municipal",
      "Secretaria de Obras",
      "Fundação de Saúde",
      "Câmara Municipal",
    ],
    templates: [
      "Contratação de serviços de manutenção predial preventiva e corretiva",
      "Serviços de manutenção elétrica, hidráulica e civil em prédios públicos",
      "Contratação de empresa para conservação de edifícios públicos",
      "Serviços de manutenção de ar condicionado e climatização",
      "Manutenção de instalações prediais em unidades de saúde",
    ],
    avgValue: 550_000,
    baseCount: 10,
  },
  materiais_eletricos: {
    orgaos: [
      "Secretaria de Obras",
      "Prefeitura Municipal",
      "Companhia de Energia",
      "Secretaria de Infraestrutura",
      "Departamento de Iluminação Pública",
    ],
    templates: [
      "Aquisição de materiais elétricos para manutenção de rede",
      "Compra de luminárias e equipamentos de iluminação pública",
      "Fornecimento de cabos, fios e materiais de instalação elétrica",
      "Aquisição de quadros de distribuição e disjuntores",
      "Compra de materiais para eficiência energética",
    ],
    avgValue: 380_000,
    baseCount: 9,
  },
  materiais_hidraulicos: {
    orgaos: [
      "Companhia de Saneamento",
      "Secretaria de Obras",
      "Prefeitura Municipal",
      "Departamento de Água e Esgoto",
      "Secretaria de Infraestrutura",
    ],
    templates: [
      "Aquisição de materiais hidráulicos para sistemas de abastecimento",
      "Fornecimento de tubos, conexões e equipamentos hidráulicos",
      "Compra de bombas e equipamentos para estação de tratamento",
      "Aquisição de materiais para rede de esgoto",
      "Fornecimento de equipamentos para sistemas de drenagem",
    ],
    avgValue: 420_000,
    baseCount: 8,
  },
  medicamentos: {
    orgaos: [
      "Secretaria de Saúde",
      "Hospital Municipal",
      "Fundação de Saúde",
      "Ministério da Saúde",
      "Farmácia Básica Municipal",
    ],
    templates: [
      "Aquisição de medicamentos para atenção básica à saúde",
      "Compra de fármacos e insumos farmacêuticos",
      "Fornecimento de medicamentos controlados para hospital",
      "Aquisição de vacinas e imunobiológicos",
      "Compra de medicamentos para programa de assistência farmacêutica",
    ],
    avgValue: 950_000,
    baseCount: 13,
  },
  mobiliario: {
    orgaos: [
      "Secretaria de Administração",
      "Prefeitura Municipal",
      "Secretaria de Educação",
      "Câmara Municipal",
      "Tribunal de Justiça",
    ],
    templates: [
      "Aquisição de mobiliário escolar para rede municipal de ensino",
      "Compra de móveis de escritório para repartições públicas",
      "Fornecimento de cadeiras, mesas e armários",
      "Aquisição de mobiliário hospitalar",
      "Compra de conjuntos de mobiliário para prédios públicos",
    ],
    avgValue: 320_000,
    baseCount: 11,
  },
  papelaria: {
    orgaos: [
      "Secretaria de Administração",
      "Prefeitura Municipal",
      "Secretaria de Educação",
      "Câmara Municipal",
      "Tribunal de Contas",
    ],
    templates: [
      "Aquisição de material de expediente e papelaria",
      "Fornecimento de materiais de escritório e consumo",
      "Compra de papel, toners e cartuchos para impressão",
      "Aquisição de materiais didáticos e escolares",
      "Fornecimento de materiais para almoxarifado",
    ],
    avgValue: 180_000,
    baseCount: 20,
  },
  servicos_prediais: {
    orgaos: [
      "Secretaria de Administração",
      "Prefeitura Municipal",
      "Fundação de Saúde",
      "Secretaria de Educação",
      "Departamento de Serviços Urbanos",
    ],
    templates: [
      "Contratação de serviços de limpeza e conservação predial",
      "Serviços de portaria, recepção e vigilância",
      "Contratação de serviços de copeiragem e garçom",
      "Serviços de jardinagem e manutenção de áreas verdes",
      "Contratação de serviços de brigada de incêndio",
    ],
    avgValue: 700_000,
    baseCount: 14,
  },
  software: {
    orgaos: [
      "Secretaria de Tecnologia da Informação",
      "Prefeitura Municipal",
      "Tribunal de Justiça",
      "Secretaria de Educação",
      "Procuradoria Geral",
    ],
    templates: [
      "Desenvolvimento de sistema de gestão administrativa",
      "Contratação de consultoria em tecnologia da informação",
      "Desenvolvimento de aplicativo para serviços públicos",
      "Serviços de manutenção e suporte de sistemas",
      "Implementação de solução de transformação digital",
    ],
    avgValue: 1_100_000,
    baseCount: 8,
  },
  transporte: {
    orgaos: [
      "Secretaria de Transportes",
      "Prefeitura Municipal",
      "Secretaria de Educação",
      "Fundação de Saúde",
      "Departamento de Logística",
    ],
    templates: [
      "Contratação de serviços de transporte escolar",
      "Serviços de transporte de pacientes para tratamento de saúde",
      "Contratação de transporte de cargas e materiais",
      "Serviços de locação de veículos com motorista",
      "Contratação de fretamento contínuo para servidores",
    ],
    avgValue: 650_000,
    baseCount: 10,
  },
  vestuario: {
    orgaos: [
      "Secretaria de Administração",
      "Polícia Militar",
      "Secretaria de Educação",
      "Prefeitura Municipal",
      "Departamento de Logística",
    ],
    templates: [
      "Aquisição de uniformes escolares para rede municipal",
      "Fornecimento de fardamentos e uniformes profissionais",
      "Compra de vestuário para servidores públicos",
      "Aquisição de EPIs de vestuário e acessórios",
      "Fornecimento de uniformes hospitalares e jalecos",
    ],
    avgValue: 280_000,
    baseCount: 12,
  },
  vigilancia: {
    orgaos: [
      "Secretaria de Administração",
      "Prefeitura Municipal",
      "Tribunal de Justiça",
      "Fundação de Saúde",
      "Banco do Estado",
    ],
    templates: [
      "Contratação de serviços de vigilância armada e desarmada",
      "Serviços de segurança patrimonial para prédios públicos",
      "Contratação de monitoramento eletrônico e alarmes",
      "Serviços de escolta e segurança de autoridades",
      "Contratação de sistema de segurança integrado",
    ],
    avgValue: 750_000,
    baseCount: 11,
  },
};

// ---------------------------------------------------------------------------
// Simulation engine
// ---------------------------------------------------------------------------

/**
 * Generates simulated opportunities based on sector and UF.
 * Produces deterministic-ish results per sector+UF combo for consistency.
 */
function generateSimulation(setorId: string, uf: string): SimulatorResult {
  const profile = SECTOR_PROFILES[setorId];
  if (!profile) {
    return { totalCount: 0, totalValue: 0, opportunities: [] };
  }

  const ufWeight = UF_WEIGHT[uf] ?? 0.3;
  const count = Math.max(2, Math.round(profile.baseCount * ufWeight));
  const totalValue = Math.round(count * profile.avgValue * (0.7 + Math.random() * 0.6));

  const opportunities: SimulatedOpportunity[] = [];
  const usedIdxs = new Set<number>();

  for (let i = 0; i < Math.min(5, count); i++) {
    let orgaoIdx: number;
    do {
      orgaoIdx = Math.floor(Math.random() * profile.orgaos.length);
    } while (usedIdxs.has(orgaoIdx) && usedIdxs.size < profile.orgaos.length);
    usedIdxs.add(orgaoIdx);

    const templateIdx = Math.floor(Math.random() * profile.templates.length);
    const valor = Math.round(
      profile.avgValue * (0.3 + Math.random() * 1.4),
    );
    const modalidade = MODALIDADES[Math.floor(Math.random() * MODALIDADES.length)];

    // Generate dates within the last 90 days + future
    const now = new Date();
    const startOffset = Math.floor(Math.random() * 60) - 10;
    const abertura = new Date(now);
    abertura.setDate(abertura.getDate() + startOffset);
    const encerramento = new Date(abertura);
    encerramento.setDate(encerramento.getDate() + 30 + Math.floor(Math.random() * 60));

    opportunities.push({
      id: i + 1,
      orgao: profile.orgaos[orgaoIdx],
      objeto: profile.templates[templateIdx],
      valor,
      modalidade,
      data_abertura: abertura.toISOString().split("T")[0],
      data_encerramento: encerramento.toISOString().split("T")[0],
      uf,
    });
  }

  return { totalCount: count, totalValue, opportunities };
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}

function TrendingUpIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
    </svg>
  );
}

function CurrencyIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

function BriefcaseIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 13.255A23.931 23.931 0 0112 15c-3.183 0-6.22-.62-9-1.745M16 6V4a2 2 0 00-2-2h-4a2 2 0 00-2 2v2m4 6h.01M5 20h14a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
    </svg>
  );
}

function CalendarIconSmall({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={2}
      aria-hidden="true"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Format helpers
// ---------------------------------------------------------------------------

function formatDateBR(dateStr: string): string {
  const [year, month, day] = dateStr.split("-");
  return `${day}/${month}/${year}`;
}

function formatCurrencyShort(value: number): string {
  if (value >= 1_000_000_000) {
    return `${(value / 1_000_000_000).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} bi`;
  }
  if (value >= 1_000_000) {
    return `${(value / 1_000_000).toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} mi`;
  }
  if (value >= 1_000) {
    return `${(value / 1_000).toLocaleString("pt-BR", { minimumFractionDigits: 0, maximumFractionDigits: 0 })} mil`;
  }
  return value.toLocaleString("pt-BR");
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function SimuladorOportunidades({
  sourcePage = "unknown",
  defaultSector = "",
  defaultUf = "",
}: SimuladorOportunidadesProps) {
  const [sector, setSector] = useState(defaultSector);
  const [uf, setUf] = useState(defaultUf);
  const [result, setResult] = useState<SimulatorResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [simulated, setSimulated] = useState(false);

  const sectorName = useMemo(
    () => SECTORS.find((s) => s.value === sector)?.label ?? sector,
    [sector],
  );

  const ufLabel = useMemo(
    () => UFS.find((u) => u.value === uf)?.label ?? uf,
    [uf],
  );

  const handleSimulate = useCallback(() => {
    if (!sector || !uf) return;

    setLoading(true);
    setSimulated(false);

    // Track simulation start
    window.mixpanel?.track("simulator_started", {
      setor: sector,
      uf,
      source_page: sourcePage,
    });

    // Simulate network delay (300-900ms)
    const delay = 300 + Math.random() * 600;

    setTimeout(() => {
      const simResult = generateSimulation(sector, uf);
      setResult(simResult);
      setLoading(false);
      setSimulated(true);

      // Track simulation completion
      window.mixpanel?.track("simulator_completed", {
        setor: sector,
        uf,
        count: simResult.totalCount,
        total_value: simResult.totalValue,
        source_page: sourcePage,
      });
    }, delay);
  }, [sector, uf, sourcePage]);

  const handleCtaClick = useCallback(
    (ctaType: "buscar" | "email_gate") => {
      window.mixpanel?.track("simulator_cta_clicked", {
        cta_type: ctaType,
        setor: sector,
        uf,
        source_page: sourcePage,
      });
    },
    [sector, uf, sourcePage],
  );

  const buscarUrl = useMemo(() => {
    const params = new URLSearchParams();
    if (sector) params.set("setor", sector);
    if (uf) params.set("uf", uf);
    return `/buscar?${params.toString()}`;
  }, [sector, uf]);

  const isFormValid = sector !== "" && uf !== "";

  return (
    <section
      aria-label="Simulador de oportunidades em licitações públicas"
      className="my-10 rounded-card border border-strong bg-surface-0 shadow-sm overflow-hidden"
      data-testid="simulador-oportunidades"
    >
      {/* Header */}
      <div className="bg-brand-navy px-6 py-5">
        <h2 className="text-lg font-bold text-white flex items-center gap-2">
          <TrendingUpIcon className="w-5 h-5" />
          Simulador de Oportunidades
        </h2>
        <p className="text-sm text-white/80 mt-1">
          Descubra quantos editais seu setor tem abertos no Brasil
        </p>
      </div>

      <div className="p-6">
        {/* Form */}
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <CustomSelect
              id="simulador-setor"
              value={sector}
              options={SECTORS}
              onChange={(v) => {
                setSector(v);
                setResult(null);
                setSimulated(false);
              }}
              label="Setor"
              placeholder="Selecione um setor"
            />
            <CustomSelect
              id="simulador-uf"
              value={uf}
              options={UFS}
              onChange={(v) => {
                setUf(v);
                setResult(null);
                setSimulated(false);
              }}
              label="UF"
              placeholder="Selecione um estado"
            />
          </div>

          <button
            type="button"
            onClick={handleSimulate}
            disabled={!isFormValid || loading}
            className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 bg-brand-blue text-white font-semibold rounded-button hover:bg-brand-blue-hover disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            data-testid="simulador-simular-btn"
          >
            {loading ? (
              <>
                <svg
                  className="animate-spin h-5 w-5"
                  fill="none"
                  viewBox="0 0 24 24"
                  aria-hidden="true"
                >
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Simulando...
              </>
            ) : (
              <>
                <SearchIcon className="w-5 h-5" />
                Simular oportunidades
              </>
            )}
          </button>
        </div>

        {/* Loading skeleton */}
        {loading && (
          <div className="mt-8 space-y-4" data-testid="simulador-loading">
            <div className="animate-pulse bg-surface-1 rounded-xl p-6">
              <div className="h-5 w-3/4 bg-surface-2 rounded mb-3" />
              <div className="h-4 w-1/2 bg-surface-2 rounded" />
            </div>
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="animate-pulse border border-strong rounded-card p-4 space-y-3"
              >
                <div className="h-4 w-1/3 bg-surface-2 rounded" />
                <div className="h-4 w-2/3 bg-surface-2 rounded" />
                <div className="h-4 w-1/4 bg-surface-2 rounded" />
              </div>
            ))}
          </div>
        )}

        {/* Results */}
        {simulated && result && result.totalCount > 0 && (
          <div className="mt-8 space-y-6 animate-fade-in" data-testid="simulador-results">
            {/* Summary banner */}
            <div className="bg-brand-blue-subtle border border-brand-blue/20 rounded-xl p-6">
              <div className="flex items-start gap-3">
                <div className="hidden sm:flex items-center justify-center w-12 h-12 rounded-full bg-brand-blue/10 shrink-0">
                  <BriefcaseIcon className="w-6 h-6 text-brand-blue" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-base sm:text-lg font-semibold text-ink">
                    <span className="text-brand-blue font-bold">{result.totalCount}</span> editais{" "}
                    encontrados em <span className="font-bold">{ufLabel.split(" (")[0]}</span>
                  </p>
                  <p className="text-sm text-ink-secondary mt-1">
                    Setor de <strong>{sectorName}</strong> nos últimos 90 dias — valor total estimado de{" "}
                    <strong className="text-brand-navy">
                      R$ {formatCurrencyShort(result.totalValue)}
                    </strong>
                  </p>
                </div>
              </div>
            </div>

            {/* Opportunity cards */}
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-ink-secondary uppercase tracking-wider">
                Oportunidades recentes
              </h3>

              {result.opportunities.map((opp) => (
                <div
                  key={opp.id}
                  className="border border-strong rounded-card p-4 hover:border-brand-blue/40 transition-colors"
                  data-testid={`simulador-card-${opp.id}`}
                >
                  <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-ink truncate">{opp.orgao}</p>
                      <p className="text-sm text-ink-secondary mt-0.5 line-clamp-2">{opp.objeto}</p>
                    </div>
                    <div className="text-left sm:text-right shrink-0">
                      <p className="text-lg font-bold font-data tabular-nums text-brand-navy">
                        {formatCurrencyBR(opp.valor)}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 mt-3 text-xs text-ink-muted">
                    <span className="inline-flex items-center gap-1">
                      <CalendarIconSmall className="w-3.5 h-3.5" />
                      {formatDateBR(opp.data_abertura)}
                    </span>
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-2 text-ink-secondary font-medium">
                      {opp.modalidade}
                    </span>
                    <span className="inline-flex items-center gap-1">
                      {opp.uf}
                    </span>
                  </div>
                </div>
              ))}
            </div>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 pt-2">
              <Link
                href={buscarUrl}
                onClick={() => handleCtaClick("buscar")}
                className="inline-flex items-center justify-center gap-2 px-6 py-3 bg-brand-blue text-white font-semibold rounded-button hover:bg-brand-blue-hover transition-colors text-center"
                data-testid="simulador-cta-buscar"
              >
                <SearchIcon className="w-5 h-5" />
                Ver editais agora
              </Link>
              <Link
                href={`/signup?source=simulador_${sourcePage}&setor=${sector}&uf=${uf}`}
                onClick={() => handleCtaClick("email_gate")}
                className="inline-flex items-center justify-center gap-2 px-6 py-3 border-2 border-brand-blue text-brand-blue font-semibold rounded-button hover:bg-brand-blue-subtle transition-colors text-center"
                data-testid="simulador-cta-email"
              >
                <CurrencyIcon className="w-5 h-5" />
                Receber relatório completo
              </Link>
            </div>
          </div>
        )}

        {/* Empty state */}
        {simulated && result && result.totalCount === 0 && (
          <div className="mt-8 text-center py-8" data-testid="simulador-empty">
            <p className="text-ink-secondary">
              Nenhum edital encontrado para este setor em {ufLabel.split(" (")[0]}.
            </p>
            <p className="text-sm text-ink-muted mt-1">
              Tente selecionar outro setor ou UF.
            </p>
          </div>
        )}
      </div>
    </section>
  );
}

export default SimuladorOportunidades;

# SERP Copy Guidelines — SmartLic Blog

**Contexto:** CTR-OPT-001. Aplicar em todos os rewrites de title/meta-description.

## Regras de Title (max 60 chars)

**Estrutura:** `[Tema específico] + [Número/dado] + [Promessa ou power word]`

- Incluir ano (2026) quando o conteúdo for temporal
- Incluir número específico quando existir ("5 Passos", "3 Cliques", "4 Erros")
- Verbo de ação ou palavra de poder no trecho mais visível
- Medir com `len()` antes de commitar — contar espaços

**Power words validadas:**
- `Descubra`, `Evite`, `Ache`, `Vença`, `Ganhe`, `Aprenda`
- `em [N] minutos`, `em [N] passos`, `em [N] cliques`
- `Prático`, `Definitivo`, `Roteiro`
- `[N] Erros que`, `[N] Critérios para`

**Anti-padrões (NÃO usar):**
- "Guia Completo" — clichê sem diferencial
- "Como fazer X" genérico sem número
- Reticências (...)
- ALL CAPS
- Adjetivos vagos: "importante", "essencial", "fundamental"

**Exemplos:**
| ❌ Antes | ✅ Depois |
|----------|----------|
| "PNCP: Guia Completo para Empresas" | "PNCP 2026: Ache Editais do Seu Setor em 5 Minutos" |
| "Como Participar de Licitações" | "1ª Licitação em 2026: 12 Passos do Cadastro ao Contrato" |
| "Licitações de TI" | "TI e Licitações 2026: 5 Critérios para Ganhar do Governo" |

## Regras de Meta Description (max 155 chars)

**Estrutura:** `[Verbo de ação + promessa específica]. [Sinal de autoridade ou prova]. [Chamada implícita]`

- Iniciar com verbo de ação (Descubra, Filtre, Aprenda, Veja, Use)
- Incluir pelo menos 1 dado concreto (número, nome de lei, %)
- Terminar com elemento de credibilidade (ex: "Atualizado 2026", "roteiro validado", "dados reais")
- NÃO repetir o title palavra por palavra
- NÃO usar "clique aqui" ou CTAs explícitos (penalização)

**Comprimento:** 120-155 chars (não deixar truncar na SERP do Google)

**Exemplos:**
| ❌ Antes | ✅ Depois |
|----------|----------|
| "Aprenda sobre o PNCP e como usá-lo para encontrar licitações." | "Filtre licitações por setor, UF e valor direto no PNCP — sem navegar em menus. 5 passos para achar o que importa. Atualizado 2026." |
| "Evite os 3 erros que eliminam propostas antes mesmo da análise. Do SICAF à entrega da proposta — roteiro completo para quem está começando." | "Do SICAF à entrega de proposta: 12 passos validados para vencer na primeira tentativa — sem erros de documentação que desclassificam propostas." |

## Regras por Intenção de Busca

| Intenção | Padrão de Title | Padrão de Description |
|----------|-----------------|----------------------|
| Informacional ("o que é X") | "[X] em 2026: [Dado específico] Explicado em [N] Passos" | "Descubra [benefício] com [dado]. [Contexto adicional]." |
| Navegacional ("como usar X") | "[X] 2026: [Ação] em [N] [tempo/passos]" | "Filtre/Use/Acesse [X] em [N] passos diretos — sem [obstáculo]." |
| Transacional ("vencer/ganhar") | "[Categoria] 2026: [N] [Critério/Passo] para [Resultado]" | "[Ação]: [dado 1], [dado 2] — o que [público] precisa para [objetivo] em 2026." |
| Comparacional ("X vs Y") | "[X] vs [Y] em 2026: [Diferencial em dado]" | "Compare [dimensão 1], [dimensão 2] e [dimensão 3] — análise objetiva com dados reais de 2026." |

## Checklist Pré-commit

- [ ] Title ≤ 60 chars? (`echo -n "title" | wc -c`)
- [ ] Description ≤ 155 chars?
- [ ] Title tem ano 2026 (se conteúdo temporal)?
- [ ] Title tem número específico?
- [ ] Description inicia com verbo de ação?
- [ ] Description inclui pelo menos 1 dado concreto?
- [ ] `alternates.canonical` preservado?
- [ ] `openGraph.images` não alterado?
- [ ] Sem typos pt-BR? (acentos, cedilha)
- [ ] Anti-padrões ausentes?

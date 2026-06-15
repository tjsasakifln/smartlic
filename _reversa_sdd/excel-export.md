# Excel Export — Fórmulas, Estilos e Estrutura

> Documentação gerada a partir de `backend/excel.py`  
> Referência: Issue #1784

---

## Planilhas Exportadas

O arquivo `.xlsx` gerado contém até 3 abas:

| Aba | Sempre presente? | Descrição |
|---|---|---|
| `Licitações Uniformes` | ✅ Sim | Dados principais das licitações |
| `Metadata` | ✅ Sim | Estatísticas da busca e totais |
| `Desbloqueie Mais` | ❌ Só no paywall preview | Upsell para SmartLic Pro |

---

## Aba: Licitações Uniformes

### Colunas (11 no total)

| Col | Header | Campo PNCP | Largura | Formato |
|---|---|---|---|---|
| A | Código PNCP | `codigoCompra` | 25 | Texto |
| B | Objeto | `objetoCompra` | 60 | Texto |
| C | Órgão | `nomeOrgao` | 40 | Texto |
| D | UF | `uf` | 6 | Texto |
| E | Município | `municipio` | 20 | Texto |
| F | Valor Estimado | `valorTotalEstimado` | 18 | Moeda `[$R$-416] #.##0,00` |
| G | Modalidade | `modalidadeNome` | 20 | Texto |
| H | Publicação | `dataPublicacaoPncp` | 12 | Data `DD/MM/YYYY` |
| I | Início | `dataAberturaProposta` | 16 | DateTime `DD/MM/YYYY HH:MM` |
| J | Situação | `situacaoCompraNome` | 15 | Texto |
| K | Link | `linkSistemaOrigem` | 15 | Hyperlink (texto: "Abrir") |

### Fórmulas

| Célula | Fórmula | Descrição |
|---|---|---|
| `F{total_row}` | `=SUM(F2:F{N})` | Soma de todos os valores estimados. Só inserida se houver ≥ 1 licitação. `N` = última linha de dados. |

### Estilos

#### Header (linha 1)
| Propriedade | Valor |
|---|---|
| Cor de fundo | `#2E7D32` (verde escuro) |
| Cor do texto | `#FFFFFF` (branco) |
| Fonte | Bold, tamanho 11 |
| Alinhamento | Centralizado horizontal e vertical, wrap text |
| Borda | `thin` em todos os lados |

#### Células de dados (linha 2+)
| Propriedade | Valor |
|---|---|
| Alinhamento | Topo vertical, wrap text |
| Borda | `thin` em todos os lados |

#### Links (coluna K)
| Propriedade | Valor |
|---|---|
| Cor do texto | `#0563C1` (azul) |
| Sublinhado | `single` |
| Texto exibido | `"Abrir"` |

#### Linha de totais
| Propriedade | Valor |
|---|---|
| Coluna E | Texto `"TOTAL:"`, bold |
| Coluna F | Fórmula SUM, bold, formato moeda |

### Comportamentos especiais

**Freeze panes:** Header fixo em `A2` — linha 1 sempre visível ao rolar.

**Sanitização de texto:** Todos os campos de texto passam por `sanitize_for_excel()` que remove caracteres de controle XML ilegais (`\x00-\x08`, `\x0b-\x0c`, `\x0e-\x1f`). Comum em dados PNCP onde em-dashes são codificados como `\x13`.

**Resolução de links (coluna K), por prioridade:**
1. `linkSistemaOrigem` (86% populado)
2. `linkProcessoEletronico` (0% — campo morto, fallback)
3. URL construída a partir de `numeroControlePNCP`:
   - Formato: `{CNPJ}-{TIPO}-{SEQUENCIAL}/{ANO}`
   - URL gerada: `https://pncp.gov.br/app/editais/{CNPJ}/{ANO}/{SEQUENCIAL}`
4. Fallback final: `https://pncp.gov.br/app/editais`

**Parsing de datas:** Tenta 3 formatos em ordem:
1. ISO 8601 com timezone (`2024-01-25T10:30:00Z`) → converte para naive (Excel não suporta tz-aware)
2. ISO 8601 sem timezone (`2024-01-25T10:30:00`)
3. Apenas data (`2024-01-25`)

---

## Aba: Metadata

| Célula A | Célula B | Condição |
|---|---|---|
| `Organização:` | `org_name` (bold, size 12) | Só se `org_name` fornecido |
| `Gerado em:` | `DD/MM/YYYY HH:MM:SS` UTC | Sempre |
| `Total de licitações:` | `int` | Sempre |
| `Valor total estimado:` | `float`, formato moeda | Calculado via `compute_robust_total()` com remoção de outliers |

---

## Aba: Desbloqueie Mais (paywall preview)

Só criada quando `paywall_preview=True` e `total_before_paywall > len(licitacoes)`.

| Célula | Conteúdo |
|---|---|
| `A1` | `"Desbloqueie {N} resultados adicionais com SmartLic Pro"` (bold, size 14, `#1A237E`) |
| `A3` | Texto informativo sobre a prévia (10 resultados) |
| `A4` | Texto com total de resultados disponíveis |
| `A6` | Hyperlink para `https://smartlic.tech/planos` |

Largura da coluna A: 80.

---

## Parâmetros de `create_excel()`

| Parâmetro | Tipo | Padrão | Descrição |
|---|---|---|---|
| `licitacoes` | `list[dict]` | obrigatório | Lista de licitações do PNCP |
| `paywall_preview` | `bool` | `False` | Ativa aba de upsell |
| `total_before_paywall` | `int \| None` | `None` | Total real antes do corte |
| `org_name` | `str \| None` | `None` | Nome da organização para metadata |

**Raises:** `ValueError` se `licitacoes` não for uma lista.

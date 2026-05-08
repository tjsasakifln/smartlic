# pSEO Title/Meta Audit — Maio 2026

**Issue:** #768 — REPO-016
**Branch:** feat/768-repo-016-pseo-meta-refresh
**Data:** 2026-05-07

---

## 1. Paginas Low-CTR (GSC, periodo ate 2026-05-06)

| URL | Impressoes | CTR | Posicao Media |
|-----|-----------|-----|--------------|
| /blog/subcontratacao-licitacoes-regras-lei-14133 | 22 | 0% | 6.7 |
| /perguntas/prazo-publicacao-edital | 22 | 0% | 6.9 |
| /blog/impugnacao-edital-quando-como-contestar | 22 | 0% | 8.6 |
| /blog/licitacoes/engenharia/ba | 14 | 0% | 5.4 |
| /blog/licitacoes/engenharia/sc | 13 | 0% | 5.2 |
| /fornecedores/53132398000186 | 12 | 0% | 5.9 |
| /blog/como-consultar-contratos-publicos-pncp | 11 | 0% | 10.3 |

### Mapeamento de Template por URL

| URL | Template | Em Escopo REPO-016? |
|-----|---------|---------------------|
| /blog/subcontratacao-licitacoes-regras-lei-14133 | blog/[slug]/page.tsx | NAO - escopo blog |
| /perguntas/prazo-publicacao-edital | perguntas/[slug]/page.tsx | NAO - escopo perguntas |
| /blog/impugnacao-edital-quando-como-contestar | blog/[slug]/page.tsx | NAO - escopo blog |
| /blog/licitacoes/engenharia/ba | blog/licitacoes/[setor]/[uf]/page.tsx | NAO - escopo blog |
| /blog/licitacoes/engenharia/sc | blog/licitacoes/[setor]/[uf]/page.tsx | NAO - escopo blog |
| /fornecedores/53132398000186 | fornecedores/[cnpj]/page.tsx | SIM - adicionado ao escopo |
| /blog/como-consultar-contratos-publicos-pncp | blog/[slug]/page.tsx | NAO - escopo blog |

**Nota:** Nenhuma das 7 URLs de baixo CTR mapeia diretamente para os 5 templates
originalmente definidos no escopo. O template /fornecedores/[cnpj] e o unico hit
direto do GSC e foi adicionado ao escopo. Os templates de blog sao candidatos
para PR futura (REPO-017 sugerido).

---

## 2. Templates Atualizados nesta PR

### 2.1 /cnpj/[cnpj]

**Antes:** "{razao_social} — Historico de Contratos Publicos"
**Depois:** "Quanto {razao_social} fatura com o governo? | SmartLic"
**Rationale:** Intencao economica alta vs titulo descritivo anterior.

### 2.2 /fornecedores/[cnpj]

**Antes:** "{razao_social} — Historico B2G | {total_contratos} contratos"
**Depois:** "Contratos publicos de {razao_social} — CNPJ {cnpj} | SmartLic"
**Rationale:** Match direto com URL de baixo CTR no GSC (pos5.9, 12imp, 0%).

### 2.3 /orgaos/[slug]

**Antes:** "{nome} — Licitacoes, Editais e Contratos"
**Depois:** "Como {nome} compra e quais oportunidades publica? | SmartLic"
**Rationale:** Pergunta direta que corresponde intencao do usuario B2G.
**Noindex preservado:** thin-content gate mantido.

### 2.4 /licitacoes/[setor]

**Antes:** "Editais de {sector.name} 2026 — Para sua Empresa | SmartLic"
**Depois:** "Melhores oportunidades para empresas de {sector.name} | SmartLic"
**Rationale:** Remove ano estatico, mais direto e orientado a resultado.
**Noindex preservado:** thin-content gate mantido.

### 2.5 /municipios/[slug]

**Antes:** "Licitacoes em {nome}-{uf} — {total} editais abertos"
**Depois:** "Licitacoes abertas {em|no} {nome}-{uf} | SmartLic"
**Preposicao UF:** DF -> "no", demais -> "em" (conforme REPO-002).

---

## 3. Templates Fora do Escopo desta PR

### 3.1 /observatorio/[slug] — DEFERIDO

Slug e date-based (raio-x-marco-2026), nao ha campo categoria.
Titulo atual ja tem intencao economica (volume de editais).
Sugestao futura: "{N} editais em {mes} {ano}: vale a pena disputar? | SmartLic"

### 3.2 Blog templates (4 URLs GSC low-CTR) — DEFERIDO para REPO-017

---

## 4. Resumo

| Template | Titulo Anterior | Titulo Novo |
|----------|----------------|-------------|
| cnpj/[cnpj] | {razao_social} — Historico de Contratos Publicos | Quanto {razao_social} fatura com o governo? | SmartLic |
| fornecedores/[cnpj] | {razao_social} — Historico B2G | {contratos} | Contratos publicos de {razao_social} — CNPJ {cnpj} | SmartLic |
| orgaos/[slug] | {nome} — Licitacoes, Editais e Contratos | Como {nome} compra e quais oportunidades publica? | SmartLic |
| licitacoes/[setor] | Editais de {setor} 2026 — Para sua Empresa | SmartLic | Melhores oportunidades para empresas de {setor} | SmartLic |
| municipios/[slug] | Licitacoes em {nome}-{uf} — N editais abertos | Licitacoes abertas {prep} {nome}-{uf} | SmartLic |

**Total: 5 templates atualizados** (4 minimo exigido + 1 bonus = fornecedores, GSC direct hit).

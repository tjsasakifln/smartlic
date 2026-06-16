---
name: "Revisao Mensal de Dependencias"
about: "Revisao mensal de vulnerabilidades e licencas das dependencias do projeto"
title: "[DEP-REVIEW] Revisao Mensal de Dependencias — YYYY-MM"
labels:
  - "dependencies"
  - "backend"
  - "frontend"
  - "security"
assignees: "tjsasakifln"
---

## Revisao Mensal de Dependencias — YYYY-MM

### Instrucoes

Seguir o procedimento documentado em `docs/development/dependency-review.md`.

### Checklist

- [ ] **pip-audit** — Rodar localmente, verificar se ha vulnerabilidades CRITICAL/HIGH alem das ja ignoradas
- [ ] **npm audit** — Rodar localmente (prod + dev), verificar se ha vulnerabilidades CRITICAL/HIGH
- [ ] **pip-licenses** — Rodar localmente, verificar se ha licencas GPL/AGPL
- [ ] **Changelogs** — Revisar changelogs de dependencias com atualizacoes major pendentes
- [ ] **Falsos positivos** — Avaliar se alguma vulnerabilidade reportada e falso positivo (justificar)
- [ ] **Ignore list** — Atualizar `docs/security/dependency-scanning.md` com novos ignores justificados (se necessario)
- [ ] **PRs necessarios** — Criar PRs para upgrades que nao sao cobertos pelo Dependabot (ex.: major versions)
- [ ] **CHANGELOG** — Atualizar se houve upgrades significativos

### Resultados

**pip-audit (OSV):** PASS / FAIL — <detalhes>
**npm audit (prod):** PASS / FAIL — <detalhes>
**npm audit (dev):** PASS / FAIL — <detalhes>
**pip-licenses:** PASS / FAIL — <detalhes>

### Acoes Tomadas

| Acao | PR/Commit | Responsavel |
|------|-----------|-------------|
|      |           |             |

### Observacoes

<!-- Adicionar observacoes sobre dependencies problematicas, upgrades pendentes, etc. -->

---

_Issue gerada automaticamente pelo template de revisao mensal de dependencias._

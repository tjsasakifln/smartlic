# Revisao Mensal de Dependencias

**Objetivo:** Garantir zero vulnerabilidades CRITICAL/HIGH e zero licencas GPL/AGPL nas dependencias do projeto, com revisao humana periodica.

**Cobertura:** Backend (Python — `backend/requirements.txt`) e Frontend (Node.js — `frontend/package.json` + `frontend/package-lock.json`).

---

## 1. Agenda

A revisao mensal ocorre na **primeira segunda-feira de cada mes**, alternando com o schedule do Dependabot (que roda semanalmente as segundas 09:00).

| Evento | Schedule | Responsavel |
|--------|----------|-------------|
| Dependabot PRs (minor/patch) | Semanal, seg 09:00 UTC | Revisao humana no PR |
| Revisao mensal completa | Primeira seg do mes | Issue template `dependency-review` |
| CI gate (pip-audit + npm audit + pip-licenses) | Diario 07:00 UTC + PR trigger | Automatizado |

---

## 2. Procedimento Passo a Passo

### 2.1 Abrir Issue de Revisao

Usar o template `.github/ISSUE_TEMPLATE/dependency-review.md` para criar a issue do mes.

### 2.2 Backend: pip-audit local

```bash
cd backend
pip install pip-audit
pip-audit --strict -r requirements.txt --desc on --format columns
```

Verificar se ha vulnerabilidades CRITICAL ou HIGH nao ignoradas. O CI gate roda automaticamente, mas a revisao humana deve conferir o changelog de cada atualizacao pendente.

### 2.3 Backend: pip-licenses local

```bash
pip install pip-licenses
pip-licenses -r backend/requirements.txt --format=json --with-authors --with-urls
```

Verificar manualmente se alguma licenca GPL/AGPL apareceu. O CI gate bloqueia automaticamente, mas a revisao humana deve avaliar se ha falsos positivos.

### 2.4 Frontend: npm audit local

```bash
cd frontend
npm ci --ignore-scripts
npm audit --audit-level=high --omit=dev
npm audit --audit-level=high  # includes devDeps (advisory)
```

### 2.5 Revisao de Changelogs

Para cada dependencia com atualizacao major pendente (ignorada pelo Dependabot config), revisar:

- Breaking changes no changelog
- Deprecations que afetam o codigo atual
- Security fixes incluidos

### 2.6 Atualizar Ignore List

Se uma vulnerabilidade conhecida nao pode ser corrigida (ex.: depende de upgrade major de framework), documentar em `docs/security/dependency-scanning.md` com o identificador CVE/PYSEC e justificativa.

### 2.7 Fechar a Issue

Apos revisar todas as dependencias:

- Marcar a issue como concluida
- Se alguma acao foi necessaria (PR de upgrade manual), referenciar o PR na issue
- Atualizar o CHANGELOG.md se houve upgrades significativos

---

## 3. CI Gates

Tres gates automaticos protegem o branch `main`:

| Gate | Workflow | Acao |
|------|----------|------|
| pip-audit | `dependency-audit.yml` | Bloqueia PR se CRITICAL/HIGH no backend |
| npm audit | `dependency-audit.yml` | Bloqueia PR se CRITICAL/HIGH no frontend (prod) |
| pip-licenses | `dependency-audit.yml` | Bloqueia PR se GPL/AGPL detectado |

Complementarmente, `dep-scan.yml` roda nos mesmos triggers com foco em PyPI advisories.

---

## 4. LGPD e Licencas

O projeto nao pode utilizar dependencias com licencas GPL ou AGPL, pois sao incompativeis com distribuicao comercial do SmartLic (LGPD compliance e restricao de licensing). Licencas permitidas incluem MIT, Apache-2.0, BSD, LGPL (com revisao caso a caso), Python Software Foundation License, e MPL-2.0.

---

## 5. Historico de Revisoes

| Data | Revisor | Principais Achados |
|------|---------|--------------------|
| — | — | _Primeira revisao pendente_ |

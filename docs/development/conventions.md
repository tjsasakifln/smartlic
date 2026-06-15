# Convenções de Código — SmartLic

**Objetivo:** Padrões consistentes para todo código do projeto.

## 1. Estilo de Código

### 1.1 Backend (Python)

**Formatter/Linter:** `ruff` (substitui black, isort, flake8)

```bash
cd backend
ruff check .          # Verificar
ruff check --fix .    # Corrigir automaticamente
```

**Type Checker:** `mypy`

```bash
mypy .
```

**Regras principais:**
- Indentação: 4 espaços
- Comprimento máximo de linha: 120 caracteres
- Docstrings: Google style (`"""Descrição.\n\nArgs:\nReturns:\n"""`)
- Type hints obrigatórios em funções públicas
- Imports absolutos (não relativos) — Article VI da Constitution

### 1.2 Frontend (TypeScript/React)

**Formatter:** Prettier (via `.prettierrc`)

```bash
cd frontend
npx prettier --check .
npx prettier --write .
```

**Linter:** ESLint (via Next.js config)

```bash
npm run lint
```

**Type Checker:** TypeScript

```bash
npx tsc --noEmit --pretty
```

**Regras principais:**
- Indentação: 2 espaços
- Comprimento máximo de linha: 100 caracteres
- Ponto e vírgula obrigatório
- Single quotes para strings
- Nomes de componentes: PascalCase
- Nomes de funções/variáveis: camelCase
- Nomes de arquivos: kebab-case

## 2. Commits (Conventional Commits)

### 2.1 Formato

```
<tipo>(<escopo>): <descrição curta>

[corpo opcional]
[rodapé opcional]
```

### 2.2 Tipos

| Tipo | Uso |
|------|-----|
| `feat` | Nova funcionalidade |
| `fix` | Correção de bug |
| `docs` | Documentação |
| `chore` | Manutenção, dependências |
| `test` | Testes |
| `refactor` | Refatoração sem mudança de comportamento |
| `perf` | Melhoria de performance |
| `style` | Formatação, estilo (sem mudança de código) |
| `ci` | CI/CD |
| `build` | Build, dependências |

### 2.3 Escopos

| Escopo | Área |
|--------|------|
| `backend` | API FastAPI |
| `frontend` | App Next.js |
| `supabase` | Database, migrations, RLS |
| `ingestion` | Pipeline de ingestão |
| `llm` | Classificação IA |
| `billing` | Stripe, planos |
| `security` | Auth, RLS, secrets |

### 2.4 Exemplos

```
feat(backend): adicionar filtro por modalidade na busca
fix(frontend): corrigir drag-and-drop no pipeline kanban
docs: atualizar guia de onboarding
chore(backend): atualizar openai para 1.109.0
test(ingestion): adicionar teste de retry para PNCP timeout
refactor(backend): extrair state machine do search-pipeline
```

## 3. Branches

### 3.1 Nomenclatura

```
feature/<descricao>     # Nova feature
fix/<descricao>         # Correção de bug
docs/<descricao>        # Documentação
chore/<descricao>       # Manutenção
test/<descricao>        # Testes
```

### 3.2 Fluxo

```
main ← feature/xxx ← commits do desenvolvedor
```

1. Criar branch de `main`: `git checkout -b feature/nova-feature main`
2. Desenvolver com commits pequenos e lógicos
3. Push: `git push origin feature/nova-feature`
4. Abrir PR no GitHub
5. Revisão + CI passando → merge

## 4. Pull Requests

### 4.1 Template

```markdown
## O que mudou

Descrição breve da mudança.

## Issue(s)

- Closes #123

## Tipo de mudança

- [ ] feat: nova funcionalidade
- [ ] fix: correção de bug
- [ ] docs: documentação
- [ ] refactor: refatoração

## Checklist

- [ ] Testes passando
- [ ] Lint passando
- [ ] Type check passando
- [ ] Cobertura mantida acima do threshold
- [ ] Documentação atualizada (se aplicável)
```

### 4.2 Review

- Todo PR precisa de pelo menos 1 review approval
- CodeRabbit review automático roda em todos os PRs
- CI gates (lint, test, build, typecheck) devem passar
- Não fazer merge com CI falhando

## 5. Testes

### 5.1 Backend (pytest)

```python
# Nome de arquivo: test_<modulo>.py
# Nome de função: test_<comportamento_esperado>

def test_busca_retorna_resultados_para_termo_valido():
    """Busca deve retornar resultados quando termo é válido."""
    ...
```

**Regras:**
- Um arquivo de teste por módulo
- Nomes descritivos (o que testa, não como implementa)
- Mock de dependências externas (Supabase, OpenAI, Stripe)
- Usar `dependency_overrides` para FastAPI
- `pytest --timeout=30` para evitar hangs (ver Anti-Hang Rules)
- Cobertura mínima: 71% (backend)

### 5.2 Frontend (Jest + React Testing Library)

```typescript
// Nome de arquivo: ComponentName.test.tsx
// Nome de teste: 'should <comportamento> when <condição>'

it('should show error message when login fails', () => {
  ...
});
```

**Regras:**
- Testar comportamento, não implementação
- Usar `screen.getByRole` preferencialmente (acessibilidade)
- Mock de API calls com MSW ou jest.mock
- Cobertura mínima: 60% (frontend)

## 6. Import Ordering

### 6.1 Backend

```python
# 1. Standard library
import asyncio
from datetime import datetime

# 2. Third-party
from fastapi import FastAPI
import httpx

# 3. Local (absoluto)
from backend.config import settings
from backend.routes.busca import router as busca_router
```

### 6.2 Frontend

```typescript
// 1. React/Next.js
import React from 'react';
import { useRouter } from 'next/router';

// 2. Third-party
import { motion } from 'framer-motion';

// 3. Local (absoluto com @)
import { Button } from '@/components/ui/Button';
import { useAuth } from '@/hooks/useAuth';
```

## 7. Nomenclatura

### 7.1 Backend

| Elemento | Convenção | Exemplo |
|----------|-----------|---------|
| Módulos | snake_case | `search_pipeline.py` |
| Classes | PascalCase | `SearchPipeline` |
| Funções | snake_case | `execute_search()` |
| Variáveis | snake_case | `search_results` |
| Constantes | UPPER_SNAKE | `MAX_RETRY_COUNT` |
| Rotas | kebab-case URL | `/api/v1/search-stats` |

### 7.2 Frontend

| Elemento | Convenção | Exemplo |
|----------|-----------|---------|
| Componentes | PascalCase | `SearchResults.tsx` |
| Hooks | camelCase + use | `useSearch.ts` |
| Utilitários | camelCase | `formatCurrency.ts` |
| Constantes | UPPER_SNAKE | `MAX_PIPELINE_COLUMNS` |
| Tipos/Interfaces | PascalCase | `BuscaResult`, `LicitacaoItem` |

## 8. Referências

- [CLAUDE.md](../../CLAUDE.md) — Regras completas de desenvolvimento
- [Guia de Setup](./setup.md)
- [API Versioning](../architecture/api-versioning.md)
- [Visão Geral da Arquitetura](../architecture/overview.md)

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>

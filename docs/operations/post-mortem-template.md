# Template de Post-Mortem — SmartLic

**Versao:** 1.0
**Criado:** 2026-06-15
**Proposito:** Documentacao padronizada de incidentes para prevencao de recorrencia.
**Uso:** Preencher para todo incidente SEV1/SEV2 em ate 48h apos resolucao.

---

## Instrucoes de Preenchimento

1. Preencher ate **48 horas** apos a resolucao do incidente.
2. Cada **Action Item** deve gerar uma GitHub Issue com label `post-mortem` e link para este documento.
3. Salvar em `docs/post-mortems/YYYY-MM-DD-slug.md`.
4. Marcar a secao **Checklist Pre-Publicacao** antes de finalizar.

---

```markdown
# Post-Mortem: [Titulo do Incidente]

**Data do Incidente:** YYYY-MM-DD
**Data do Post-Mortem:** YYYY-MM-DD
**Severidade:** SEV1 / SEV2
**Duracao:** HH:MM ate HH:MM UTC (Xh Ym)
**Impacto:** [Breve descricao do impacto ao usuario/negocio]
**Responsavel pelo Post-Mortem:** [Nome]
**Revisores:** [Nome1, Nome2]

---

## 1. Timeline (UTC)

| Horario | Evento |
|---------|--------|
| HH:MM | [Primeiro sinal — alerta Sentry, health check, usuario reportando] |
| HH:MM | [Investigacao iniciada — quem, o que verificou] |
| HH:MM | [Causa raiz identificada] |
| HH:MM | [Mitigacao aplicada — feature flag, rollback, hotfix] |
| HH:MM | [Confirmacao de resolucao — health check OK, metricas normalizadas] |
| HH:MM | [Post-mortem iniciado / comunicacao as partes interessadas] |

> Todos os horarios em UTC. Converter de logs Railway/Sentry/Stripe conforme necessario.

## 2. 5-Whys — Analise de Causa Raiz

**Problema:** [O que deu errado? Ex: backend wedged, usuarios recebendo 502]

1. **Por que?** [Primeira causa imediata]
   - Evidencia: [log, metrica, commit]
2. **Por que?** [Causa subjacente]
   - Evidencia: [log, metrica, commit]
3. **Por que?** [Causa sistemica]
   - Evidencia: [log, metrica, commit]
4. **Por que?** [Falha de processo/arquitetura]
   - Evidencia: [log, metrica, commit]
5. **Por que?** [Falha organizacional/sistemica raiz]
   - Evidencia: [log, metrica, commit]

**Causa Raiz:** [Frase unica resumindo os 5-whys]

## 3. Impacto

| Metrica | Valor |
|---------|-------|
| Usuarios afetados | [numero ou estimativa] |
| Duracao da indisponibilidade | [Xh Ym] |
| Requests com erro (5xx) | [N] |
| Erros no Sentry | [N eventos] |
| Receita afetada | [R$ estimado ou N/A] |
| Componentes afetados | [backend, frontend, worker, banco, etc] |
| Commits de hotfix | [hash1, hash2] |

## 4. Resposta ao Incidente

| Fase | Duracao | Observacao |
|------|---------|------------|
| Deteccao ate diagnostico | [min] | O que atrasou? |
| Diagnostico ate mitigacao | [min] | O que funcionou? |
| Mitigacao ate resolucao total | [min] | O que poderia ser mais rapido? |
| **MTTR total** | **Xh Ym** | |

### O Que Funcionou Bem

- [Ex: Circuit breaker impediu cascata para outras fontes]
- [Ex: Feature flag permitiu desabilitar funcao sem deploy]

### O Que Poderia Ser Melhor

- [Ex: Nao havia alerta para essa metrica especifica]
- [Ex: Documentacao do runbook estava desatualizada]

## 5. Action Items

Cada item deve gerar uma **GitHub Issue** com label `post-mortem` + link para este post-mortem.

| # | Acao | Tipo | Responsavel | Prazo | Issue |
|---|------|------|-------------|-------|-------|
| 1 | [Descricao concisa] | preventiva / corretiva / monitoramento | [@user] | YYYY-MM-DD | [#NNN] |
| 2 | [Descricao concisa] | preventiva / corretiva / monitoramento | [@user] | YYYY-MM-DD | [#NNN] |

**Tipos de acao:**
- **preventiva:** Impede que a mesma causa raiz ocorra novamente.
- **corretiva:** Corrige danos ou lacunas deixadas pelo incidente.
- **monitoramento:** Adiciona alerta, metrica ou observabilidade para deteccao precoce.

## 6. Licoes Aprendidas

1. [Licao 1 — o que o time aprendeu sobre o sistema]
2. [Licao 2 — o que o time aprendeu sobre o processo de resposta]
3. [Licao 3 — o que deve ser diferente no proximo incidente]

---

## Checklist Pre-Publicacao

- [ ] Timeline verificada contra logs reais (Sentry, Railway, Stripe)
- [ ] Action items tem responsavel e prazo definidos
- [ ] Cada action item tem uma GitHub Issue criada com label `post-mortem`
- [ ] Link para este post-mortem adicionado em cada Issue criada
- [ ] Aprovado por pelo menos 1 revisor
- [ ] Salvo em `docs/post-mortems/YYYY-MM-DD-slug.md`
```

---

## Referencias

- `docs/operations/incident-response.md` — processo completo de resposta a incidentes
- `docs/operations/alerting-runbook.md` — runbooks por tipo de alerta
- `docs/runbook/incident-response.md` — runbook detalhado de resposta

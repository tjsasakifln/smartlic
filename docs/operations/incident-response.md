# Processo de Resposta a Incidentes — SmartLic

**Versao:** 1.0
**Ultima atualizacao:** 2026-06-15
**Responsavel:** Tiago Sasaki (tiago.sasaki@gmail.com)
**Produto:** SmartLic (https://smartlic.tech)
**Issues:** #1799 (runbook), #1878 (post-mortem)

---

Este documento define o **fluxo de ponta a ponta** da resposta a incidentes: desde a deteccao ate o post-mortem e fechamento dos action items.

Para procedimentos **taticos** (diagnostico, mitigacao, rollback por tipo de alerta), consulte `docs/runbook/incident-response.md`.

---

## 1. Ciclo de Vida do Incidente

```
Deteccao → Classificacao → Investigacao → Mitigacao → Resolucao
                                                              ↓
                                                     Post-Mortem (48h)
                                                              ↓
                                                     Action Items → Issues
                                                              ↓
                                                     Verificacao (30d)
```

### 1.1 Deteccao

| Canal | Exemplo | Acao |
|-------|---------|------|
| Alerta Sentry | Error rate > 5%, Circuit Breaker Open | Abrir incidente |
| Alerta UptimeRobot | /health retornando 503 | Verificar logs Railway |
| Alerta Stripe | Webhook falhando | Verificar Stripe Dashboard |
| Usuario reportando | "Nao consigo buscar" | Verificar /health + logs |
| CI/CD falhando | Deploy travado, migracao pendente | Verificar GitHub Actions + Railway |

### 1.2 Classificacao de Severidade

| Nivel | Nome | Exemplo | MTTR Alvo |
|-------|------|---------|-----------|
| **SEV1** | Indisponibilidade Total | Backend wedged, Supabase down, billing quebrado | < 30min |
| **SEV2** | Degradacao Maior | Circuit breaker aberto, fonte primaria fora, pool saturado | < 2h |
| **SEV3** | Degradacao Menor | LLM classification falhando (fallback ativo), erro cosmetico | < 24h |
| **SEV4** | Baixo Impacto | Log excessivo, metrica inconsistente, alerta ruidoso | Proximo sprint |

**Criterios de escalonamento:**
- SEV3 sem resolucao em 4h → SEV2
- SEV2 sem resolucao em 2h → SEV1
- Qualquer incidente afetando billing → automaticamente SEV1

### 1.3 Resposta Imediata

1. Classificar severidade (SEV1-SEV4)
2. Verificar `/health/live` e `/health/ready`
3. Verificar logs Railway: `railway logs --tail --service bidiq-backend`
4. Verificar Sentry para stack traces recentes
5. Identificar feature flag para mitigacao rapida (ver `docs/runbook/incident-response.md` secao Feature Flags)
6. Aplicar mitigacao (feature flag, rollback, restart)
7. Confirmar resolucao via health checks
8. Comunicar status (email/Slack se SEV1/SEV2)

### 1.4 Criterios de Post-Mortem Obrigatorio

Post-mortem (conforme template em `docs/operations/post-mortem-template.md`) e obrigatorio para:

- **Todo incidente SEV1** — sem excecao
- **Todo incidente SEV2** — sem excecao
- **Incidentes SEV3 recorrentes** — mesma causa 2+ vezes no mesmo mes
- **A criterio do responsavel** — para incidentes com licoes importantes

---

## 2. Processo de Post-Mortem

Prazo maximo: **48 horas** apos a resolucao do incidente.

### 2.1 Fluxo

```
Resolucao do incidente
        ↓ (imediatamente)
Coleta de evidencias: logs, metricas, timeline
        ↓ (ate 24h)
Rascunho do post-mortem usando template padrao
        ↓ (ate 36h)
Revisao com pelo menos 1 revisor
        ↓ (ate 48h)
Publicacao em docs/post-mortems/YYYY-MM-DD-slug.md
        ↓
Criacao de GitHub Issues para cada action item
        ↓ (30 dias)
Verificacao de fechamento dos action items
```

### 2.2 Estrutura do Post-Mortem

O template completo esta em `docs/operations/post-mortem-template.md`. Secoes obrigatorias:

1. **Timeline (UTC)** — Linha do tempo evento a evento com horarios extraidos de logs
2. **5-Whys** — Analise de causa raiz em 5 niveis de profundidade
3. **Impacto** — Usuarios afetados, duracao, severidade, metricas de erro
4. **Action Items** — Cada item vira uma GitHub Issue com label `post-mortem`
5. **Licoes Aprendidas** — O que funcionou, o que melhorar, o que faltou

### 2.3 Action Items como GitHub Issues

Cada action item do post-mortem deve:

1. Ser criado como **GitHub Issue** no repositorio
2. Receber a **label `post-mortem`**
3. Incluir no corpo da issue o **link para o post-mortem** completo
4. Ter **responsavel** e **prazo** definidos
5. Ser categorizado como **preventiva**, **corretiva** ou **monitoramento**

Exemplo de corpo de Issue:

```
## Action Item - [Titulo]

**Origem:** Post-Mortem de [data] — [link para post-mortem]
**Tipo:** preventiva
**Responsavel:** @user
**Prazo:** YYYY-MM-DD

### Descricao

[... descricao detalhada do que precisa ser feito ...]

### Criterios de Aceitacao

- [ ] ACA 1
- [ ] ACA 2

### Referencias

- Post-Mortem: docs/post-mortems/YYYY-MM-DD-slug.md
- Secao 5, Action Item #N
```

### 2.4 Verificacao de Action Items (30 dias)

A cada 30 dias, revisar as issues abertas com label `post-mortem`:

- Issues fechadas: verificar que a resolucao foi efetiva
- Issues atrasadas: renegociar prazo ou escalar
- Issues canceladas: documentar justificativa no proprio post-mortem

---

## 3. Arquivo de Post-Mortems

Post-mortems sao salvos em `docs/post-mortems/YYYY-MM-DD-slug.md`.

Convencao de nomenclatura:

```
docs/post-mortems/YYYY-MM-DD-descricao-curta.md
```

Exemplos:

```
docs/post-mortems/2026-04-27-backend-wedge.md
docs/post-mortems/2026-04-10-googlebot-crawl-saturation.md
```

### Post-Mortems Realizados

| Data | Incidente | Link |
|------|-----------|------|
| [Adicionar apos cada post-mortem] | | |

---

## 4. Metricas de Efetividade

| Metrica | Alvo | Como Medir |
|---------|------|------------|
| MTTR SEV1 | < 30min | Tempo entre deteccao e resolucao |
| MTTR SEV2 | < 2h | Tempo entre deteccao e resolucao |
| Post-mortem em 48h | 100% SEV1/SEV2 | Data do post-mortem vs data do incidente |
| Action items fechados em 30d | > 80% | Issues label `post-mortem` fechadas vs total |
| Incidentes recorrentes | 0 | Mesma causa raiz em incidentes distintos |

---

## 5. Referencias

| Documento | Conteudo |
|-----------|----------|
| `docs/operations/post-mortem-template.md` | Template padrao de post-mortem |
| `docs/operations/alerting-runbook.md` | Inventario de alertas e runbooks por alerta |
| `docs/runbook/incident-response.md` | Runbook tatico de resposta (diagnostico, mitigacao, rollback) |
| `docs/runbooks/general-outage.md` | Procedimento para outage geral |
| `docs/runbooks/audit-prod-env.md` | Auditoria de env vars em producao |
| `docs/operations/monitoring.md` | Monitores de uptime e health checks |
| `CLAUDE.md` | Secao Troubleshooting + CRIT-080/083/084 |

---

## Historico de Alteracoes

| Data | Versao | Descricao |
|------|--------|-----------|
| 2026-06-15 | 1.0 | Documento criado: processo de resposta + post-mortem flow (#1878) |

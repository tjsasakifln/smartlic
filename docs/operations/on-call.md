# On-Call Rotation — SmartLic

> AC5: Weekly on-call rotation, escalation contacts, and schedule.
> Ultima atualizacao: 2026-06-15

---

## 1. Current Rotation

| Semana | Periodo | Primary | Secondary | Escalation |
|--------|---------|---------|-----------|------------|
| 1 | 2026-06-15 a 2026-06-21 | Tiago Sasaki | Marinalva Baron | Tiago Sasaki |
| 2 | 2026-06-22 a 2026-06-28 | Marinalva Baron | Tiago Sasaki | Tiago Sasaki |
| 3 | 2026-06-29 a 2026-07-05 | Tiago Sasaki | Marinalva Baron | Tiago Sasaki |
| 4 | 2026-07-06 a 2026-07-12 | Marinalva Baron | Tiago Sasaki | Tiago Sasaki |

**Legenda:**
- **Primary:** Responde primeiro. SLA 5min para SEV1.
- **Secondary:** Backup se primary nao responder em 5min.
- **Escalation:** Acionado se secondary nao responder em 15min.

### Contatos

| Nome | Email | Telefone | PagerDuty |
|------|-------|----------|-----------|
| Tiago Sasaki | tiago.sasaki@gmail.com | (11) 99999-9999 | PD: tiago.sasaki@smartlic.tech |
| Marinalva Baron | marinalvabaron@gmail.com | (11) 98888-8888 | PD: marinalva.baron@smartlic.tech |

---

## 2. Responsabilidades do On-Call

### Durante o Turno
1. **Responder a alertas SEV1** em < 5 minutos (medido do disparo ao ack).
2. **Triar alertas SEV2** em < 15 minutos (Slack #alerts).
3. **Iniciar playbook** de acordo com o tipo de alerta (ver `incident-playbook.md`).
4. **Atualizar status** no canal `#incident-response` a cada 30 min enquanto o incidente estiver ativo.
5. **Registrar post-mortem** dentro de 48h apos resolucao (template em `docs/operations/post-mortem-template.md`).

### Handoff
- Handoff ocorre toda **segunda-feira as 10:00 BRT**.
- O primary de saída deve:
  1. Revisar incidentes ativos e transferir contexto.
  2. Atualizar alertas nao resolvidos para o novo primary.
  3. Enviar resumo no canal `#operations`.
- O primary de entrada confirma recebimento no mesmo canal.

---

## 3. Escalation Path

```
SEV1 disparado
    │
    ├─ 0 min: PagerDuty notifica Primary (push + SMS)
    ├─ 5 min: Se NAO acknowledged → escala para Secondary
    │           Slack @here + Sentry error
    ├─ 15 min: Se NAO acknowledged → escala para Escalation
    │           Slack @channel + Sentry fatal
    │           Email para founders@smartlic.tech
    └─ 30 min: Se NAO acknowledged → Procedimento de Emergencia
                (restart forçado via Railway CLI)
```

---

## 4. Canais de Comunicacao

| Canal | Proposito | Onde |
|-------|-----------|------|
| `#incident-response` | Coordenacao de incidentes ativos | Slack SmartLic |
| `#alerts` | Notificacoes de alerta automatizadas | Slack SmartLic |
| `#operations` | Handoff, mudancas, operacoes | Slack SmartLic |
| PagerDuty | Push notification + SMS para SEV1 | PagerDuty SmartLic |
| Email founders | Falha de escalation apos 15min | founders@smartlic.tech |

---

## 5. Configuracao de Ferramentas

### PagerDuty
1. Schedule: `smartlic-on-call` (semanal, rotacao A/B).
2. Escalation policy: `smartlic-sev1` (5min primary → 5min secondary → 15min escalation).
3. Service: `smartlic-backend` integrado a `PAGERDUTY_ROUTING_KEY`.
4. Notifications: Push + SMS + phone call.

### Opsgenie (alternativa gratuita)
Se PagerDuty nao estiver disponivel:
1. Criar team `SmartLic` em opsgenie.com.
2. Schedule: rotacao semanal com 2 users.
3. Escalation: `smartlic-sev1-policy` (5min → 15min).
4. Integrar via `OPSGENIE_API_KEY` + `OPSGENIE_REGION`.

### Slack
1. Canais `#alerts` e `#incident-response` criados.
2. Slack webhook configurado em `SLACK_ALERTS_WEBHOOK_URL`.
3. Bot `SmartLic Alerts` posta mensagens formatadas com severity color.

---

## 6. Metricas de Efetividade

| Metrica | Target | Medicao |
|---------|--------|---------|
| Time to Acknowledge (TTA) | < 5 min SEV1 | PagerDuty analytics |
| Time to Resolve (TTR) | < 60 min SEV1 | Sentry + PagerDuty |
| MTTR (mensal) | < 120 min | Post-mortem log |
| Escalation rate | < 10% dos SEV1 | alert_manager metrics |
| Alerts sem ack | 0 | Slack audit log |

---

## 7. Historico

| Data | Alteracao |
|------|-----------|
| 2026-06-15 | Documento criado (Issue #1865) |

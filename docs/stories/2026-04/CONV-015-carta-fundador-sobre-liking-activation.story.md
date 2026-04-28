# CONV-015: Carta do fundador em /sobre + Liking activation

**Status:** Ready
**Origem:** Consenso /copymasters 2026-04-28 (Cluster Psicologia/Cialdini Liking + Cluster Brasileira/Olivetto)
**Prioridade:** P3
**Complexidade:** S (1 dia escrita + 0.5 dia implementação)
**Owner:** @copywriter (Tiago direto) + @dev
**Tipo:** Content / Frontend
**Epic:** EPIC-CONV-FUNNEL-2026-Q2

---

## Contexto

Memory `reference_resend_personal_tone_send`: tom pessoal funciona em SmartLic (founder-led email + reply-to gmail). Cialdini Liking principle: pessoas confiam mais em quem percebem como "humano relatable" vs corporate faceless.

Pre-revenue B2G brasileiro: founder visibility é assimetricamente impactante. Olivetto "emoção invisível": carta pessoal que parece não ter autor publicitário converte mais que copy polido.

SmartLic não tem `/sobre` com carta do Tiago. Página `/sobre` atual (verificar se existe) provavelmente é genérica corporate.

---

## Decisão

1. Tiago escreve carta pessoal em primeira pessoa: experiência B2G, por que SmartLic existe, mission, compromissos
2. Foto real + assinatura digitalizada
3. Página `/sobre` redesenhada com carta como conteúdo principal
4. Linkar de footer + email signature + autoresponder
5. Tom: como se fosse email pessoal para um colega — não corporate

---

## Critérios de Aceite

### Conteúdo

- [ ] **AC1:** Carta escrita em pt-BR primeira pessoa, max 600 palavras, contendo:
  - Quem é Tiago (background B2G, anos de experiência, dor pessoal vivida)
  - Por que SmartLic existe (problema percebido, momento de decisão)
  - O que SmartLic NÃO é (ex: "não somos planilha glorificada nem consultor automatizado")
  - Compromissos com cliente (uptime, dados, suporte direto, sem letras miúdas)
  - Convite explícito ("se você é dono de empresa B2G, me responde — leio todos os emails")
  - Email pessoal `tiago.sasaki@gmail.com` ou WhatsApp business

- [ ] **AC2:** Tom não corporate — fragmentos OK, parágrafos curtos, vocabulário do Tiago
- [ ] **AC3:** Foto real do Tiago em alta qualidade (face shot ou half-body em ambiente real, não foto de stock)
- [ ] **AC4:** Assinatura digitalizada (handwritten "— Tiago Sasaki, Fundador") em SVG ou PNG transparente

### Página `/sobre`

- [ ] **AC5:** Página `/sobre` redesenhada com:
  - Carta como conteúdo principal (centro)
  - Foto Tiago lateral ou topo
  - Assinatura ao final
  - CTA "Falar com Tiago direto" (link wa.me OR mailto)
  - Links secundários: "Termos" (`/termos`), "Privacidade" (`/privacidade`), "LGPD" (`/lgpd-compliance` se CONV-014 done)

- [ ] **AC6:** Layout typográfico: leitura confortável (max-width 65ch), font-size legível (16-18px), line-height generoso (1.7+)

### Distribuição

- [ ] **AC7:** Footer global: link "Sobre" → `/sobre` (já deve existir, validar)
- [ ] **AC8:** Email autoresponder + signature dos emails Resend (templates em `backend/templates/emails/`) incluem footer:
  ```
  --
  Tiago Sasaki — Fundador SmartLic
  Sobre nós: smartlic.tech/sobre
  Email direto: tiago.sasaki@gmail.com
  ```

### SEO

- [ ] **AC9:** Meta tags `/sobre`:
  - Title: "Sobre o SmartLic — Tiago Sasaki, Fundador"
  - Description: 1-2 frases da carta, ~150 chars
  - OG image: foto Tiago

- [ ] **AC10:** Schema.org `Person` markup com nome, cargo, foto, sameAs (LinkedIn se existir)

### Tracking

- [ ] **AC11:** Mixpanel event `sobre_view` (page view)
- [ ] **AC12:** Mixpanel event `sobre_cta_click` para WhatsApp/email direct contact

---

## Arquivos Impactados

**Novos OU Modificados:**
- `frontend/app/sobre/page.tsx` — redesign completo (verificar se já existe)
- `public/founder/tiago-photo.jpg` (ou .webp)
- `public/founder/tiago-signature.svg`
- `frontend/components/about/FounderLetter.tsx` — componente da carta
- `backend/templates/emails/_signature.html` — partial reutilizável
- `frontend/components/layout/Footer.tsx` — confirmar link `/sobre` existe

**Modificados:**
- Templates email em `backend/templates/emails/*.html` — incluir signature partial
- `frontend/lib/seo/metadata.ts` (se existir) — meta para `/sobre`

---

## Riscos

- **R1 (Baixo):** Tiago precisa investir tempo escrevendo carta autêntica (não delegar 100% para copywriter). **Mitigação:** copywriter entrevista Tiago + edita; Tiago revisa e ajusta. ~2h Tiago.
- **R2 (Baixo):** Foto pode estar desatualizada em 1 ano. **Mitigação:** revisar trimestralmente.
- **R3 (Baixo):** WhatsApp direto pode receber spam se publicado. **Mitigação:** AC8 prefer wa.me com pré-mensagem para filtragem.

---

## Dependências

- Tiago disponibilidade (~2h escrita + revisão)
- Foto profissional (existente OU shoot novo)
- CONV-001 (instrumentação) Done

---

## Change Log

| Data | Agente | Ação |
|------|--------|------|
| 2026-04-28 | @sm | Story criada via consenso /copymasters. P3 do EPIC-CONV-FUNNEL-2026-Q2. Princípio Cialdini Liking + Olivetto emoção invisível. Status=Draft → @po validation |
| 2026-04-28 | @po | Validation 9/10 → **GO**. ~2h Tiago + 0.5d @dev. Conteúdo personalístico + foto real + signature + email signature partial. AC10 schema.org Person para SEO. Status Draft → Ready. |

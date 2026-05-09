# Spec: Intel Report — PDF Generator `pdf_generator_sector_uf_report`

> Sub-spec do contrato PDF executável do INTEL-REPORT-002 v0.2.
> Confiança: 🟢 CONFIRMADO (código shipped via PR #826/#825 + 34 unit tests).
> Story: `INTEL-REPORT-002-V02-SPEC-001`. Companion: [`07-intel-report-sector-uf.md`](./07-intel-report-sector-uf.md), [`13-intel-reports.spec.md`](./13-intel-reports.spec.md).

## Component

- **ID**: `intel-report-sector-uf-pdf-generator`
- **Tipo**: Python function — síncrona, retorna `BytesIO` posicionado em `seek(0)`.
- **Path**: `backend/pdf_generator_sector_uf_report.py` (732 LOC).
- **Função pública**: `generate_sector_uf_report(db: Any, entity_key: str) -> BytesIO`.

## Purpose

Gera PDF A4 multi-seção a partir do payload retornado pela RPC `sector_uf_intel`. Output é **byte stream** — não escreve em disco, deixa o caller (ARQ job `generate_intel_report` em `jobs/queue/jobs.py`) fazer upload para Supabase Storage no path `{user_id}/{purchase_id}.pdf`.

ReportLab `SimpleDocTemplate` com paleta brand `#1B3A5C` (BRAND_DARK_BLUE) — alinhada a `pdf_generator_intel_report.py` (Raio-X Concorrente v0.1).

## Input Contract

| Parâmetro | Tipo | Schema |
|-----------|------|--------|
| `db` | `Any` | Cliente Supabase service-role (`supabase_client.get_supabase()`). Usado apenas em `_fetch_rpc_data` para chamar `db.rpc("sector_uf_intel", {...}).execute()`. |
| `entity_key` | `str` | Formato `"sector_id:UF"` — e.g. `"limpeza:SP"`, `"construcao:RJ"`. `sector_id` deve ser key válida em `backend/sectors_data.yaml`; UF é 2 letras. |

### Resolução interna

```
entity_key = "limpeza:SP"
  → sector_id="limpeza", uf="SP"
  → keywords = sectors.get_sector("limpeza").keywords        # backend/sectors.py
  → sector_label = sector.name (e.g. "Limpeza e Conservação")
  → db.rpc("sector_uf_intel", {p_sector, p_keywords, p_uf, p_window_months: 24})
  → data dict ← _fetch_rpc_data unwrap
  → data["sector_label"] = sector_label  (enrich for cover)
```

## Output Contract

| Característica | Valor |
|----------------|-------|
| Tipo | `BytesIO` |
| Position | `seek(0)` (validado em `test_returned_bytesio_seeked_to_start`) |
| MIME | `application/pdf` |
| Tamanho típico | ~30-200 KB (depende top_fornecedores/orgaos populated) |
| Page size | A4 (210×297 mm) |
| Margins | 2 cm L/R, 1.5 cm top, 2.5 cm bottom |
| PDF metadata | `title="SmartLic Intelligence — Panorama {sector_label} × {uf}"`, `author="SmartLic"` |
| Footer | `"SmartLic Intelligence — smartlic.tech \| Dados: PNCP \| Atualizado em {DD/MM/YYYY}"` + página atual |

## Section Builders

PDF assembly via `doc.build([cover, exec_summary, top_fornecedores, top_orgaos, temporal, top_objetos, esfera])`:

| Função | Saída |
|--------|-------|
| `_build_cover` (linhas 236-291) | Page 1 — logo SmartLic Intelligence + HRFlowable BRAND_ACCENT, título "Panorama Setorial", subtítulo `{sector_label} — {uf}`, janela 24m, geração date. PageBreak final. |
| `_build_executive_summary` (linhas 292-354) | Metric boxes (METRIC_BOX_BG `#EFF6FF`): total_contracts, total_value, avg_ticket, median_ticket, p90_ticket, data_primeiro/ultimo. |
| `_build_top_fornecedores` (linhas 374-423) | Table até 20 rows: ni_fornecedor, nome_fornecedor, count, valor_total, avg_ticket. |
| `_build_top_orgaos` (linhas 424-470) | Table até 10 rows: orgao_cnpj, orgao_nome, count, valor_total. |
| `_build_temporal_evolution` (linhas 471-512) | Série mensal `serie_temporal` (zero-fill RPC-side). |
| `_build_top_objetos` (linhas 513-547) | Table até 10 rows: objeto_resumo (LEFT 80 chars), count, valor_total. |
| `_build_esfera_distribution` (linhas 548-594) | Distribuição F/E/M/D (`ESFERA_LABELS` dict linhas 65-70). |

## Helper Contract

| Helper | Contrato | Test coverage |
|--------|----------|---------------|
| `_sanitize(value)` | `None → ""`, strip `\x00-\x1f` exc. tab/LF, `html.escape`. | `test_sanitize_none_returns_empty/strips_control_chars/escapes_html` |
| `_fmt_currency(v)` | `None → "—"`, `0 → "R$ 0,00"`, `1234.56 → "R$ 1.234,56"`, invalid → `"—"`. | `test_fmt_currency_none/zero/positive/invalid` |
| `_fmt_int(v)` | `1234 → "1.234"`, invalid → `"—"`. | `test_fmt_int_valid/invalid` |
| `_fmt_pct(v)` | `12.345 → "12.3%"`, None → `"—"`. | `test_fmt_pct_valid/none` |
| `_format_date("2024-05-08")` | `"08/05/2024"`. ISO 8601 com `T` sufixo OK. | `test_format_date_valid_iso/none/with_time_component` |
| `_trunc(s, max=80)` | Strings ≤80 inalteradas; >80 truncadas com `…`. | `test_trunc_short_string_unchanged/long_string_truncated` |

## Error Modes

| Trigger | Exception | Site |
|---------|-----------|------|
| `entity_key` sem `:` | `ValueError("Invalid entity_key {!r}. Expected format 'sector_id:UF'")` | linha 654-656 |
| `sector_id` vazio ou UF length ≠ 2 | `ValueError("Invalid entity_key {!r}. sector_id must be non-empty and UF must be 2 letters.")` | linha 661-665 |
| `sector_id` não existe em `sectors_data.yaml` | `ValueError("Cannot resolve keywords for sector {!r}: {exc}")` | linha 673-676 |
| RPC retorna `[]` ou `None` | `ValueError("sector_uf_intel returned no data for sector={!r} uf={!r}")` | linha 612-615 |
| RPC retorna shape inesperado (não list/dict) | `ValueError("sector_uf_intel returned unexpected shape: {type}")` | linha 628-630 |
| ReportLab `doc.build` exception | propagada (caller ARQ job marca `failed` + refund auto + email apologetic — `jobs.py:_send_intel_report_failed_email` linhas 223-256) |

## Caller Flow (ARQ)

```python
# backend/jobs/queue/jobs.py:125-150
async def _generate_sector_uf_report_pdf(db, entity_key) -> bytes:
    from pdf_generator_sector_uf_report import generate_sector_uf_report
    buffer = generate_sector_uf_report(db=db, entity_key=entity_key)
    return buffer.getvalue()

async def _generate_intel_report_pdf(db, purchase) -> bytes:
    if purchase["product_type"] == "sector_uf":
        return await asyncio.wait_for(
            _generate_sector_uf_report_pdf(db, purchase["entity_key"]),
            timeout=90,  # 6× folga sobre RPC statement_timeout 15s
        )
```

## Test Coverage

`backend/tests/test_sector_uf_intel_pdf.py` — **34 testes** distribuídos:

| Classe | Quantidade | Foco |
|--------|-----------|------|
| `TestHelpers` | 16 | `_sanitize`, `_fmt_currency`, `_fmt_int`, `_fmt_pct`, `_format_date`, `_trunc` |
| `TestSectionBuilders` | 7 | `_build_cover` (com/sem UF, page break), `_build_executive_summary`, `_build_top_fornecedores` (with/empty/None) |
| `TestGenerateSectorUfReport` | 11 | E2E PDF generation, BytesIO seek, empty sections, entity_key validation (no colon, empty sector, invalid UF), RPC error modes (empty list, None, sector not found, wrong params, dict payload direct) |

Run: `pytest backend/tests/test_sector_uf_intel_pdf.py -v`. Status atual: 34 passing (PR #825 fix).

## Invariants

1. **Output BytesIO sempre posicionado em `seek(0)`** (linha 731). Garantia para upload `bucket.upload(file=pdf_bytes)`.
2. **Sem dependência de filesystem** — entrada e saída em memória apenas.
3. **Sem requests externos** além do `db.rpc(...).execute()` único.
4. **Brand colors hardcoded** (linhas 43-55) — sincronizadas com `pdf_generator_intel_report.py` (Raio-X v0.1).
5. **Helpers duplicados intencionalmente** (linhas 73-74 docstring) — mantém modules independentes (não importa de `pdf_generator_intel_report`).

## Functional Requirements

- **FR-1**: `generate_sector_uf_report(db, "limpeza:SP")` retorna `BytesIO` com PDF A4 válido.
- **FR-2**: PDF inclui 7 seções (cover, executive_summary, top_fornecedores, top_orgaos, temporal, top_objetos, esfera).
- **FR-3**: Empty agregados (zero contratos no recorte) ainda geram PDF (cover + sections com `(sem dados)` placeholders) — `test_empty_sections_still_generates_pdf`.
- **FR-4**: PDF metadata `title` populado com `sector_label × uf`.
- **FR-5**: Footer em todas as páginas (`onFirstPage=_footer, onLaterPages=_footer`).

## Non-Functional Requirements

- **NFR-1**: Synchronous function — caller faz `asyncio.to_thread` se necessário (ARQ job já é I/O-bound concorrente).
- **NFR-2**: Memória peak <50MB para PDF típico.
- **NFR-3**: Wall-clock <30s para payload típico (RPC 15s + ReportLab build ~1-3s).
- **NFR-4**: Texto sanitizado contra XML injection (`html.escape` + strip control chars).

## Acceptance Criteria

- **AC-1**: 34 testes em `test_sector_uf_intel_pdf.py` passam green.
- **AC-2**: ARQ job `generate_intel_report` para `product_type='sector_uf'` upload PDF para Storage path `{user_id}/{purchase_id}.pdf` e marca `intel_report_purchases.status='ready'`.
- **AC-3**: Email Resend (`send_intel_report_ready` em `backend/email_service.py`) entregue com signed URL 30d TTL.
- **AC-4**: Erro de geração → refund Stripe automático + email apologetic (`_refund_intel_report_purchase` + `_send_intel_report_failed_email` em `jobs.py:199-256`).

## Code Traceability

- **Module**: `backend/pdf_generator_sector_uf_report.py` (732 LOC)
- **Tests**: `backend/tests/test_sector_uf_intel_pdf.py` (366 LOC, 34 tests)
- **ARQ adapter**: `backend/jobs/queue/jobs.py:_generate_sector_uf_report_pdf` (linhas 125-134) + `_generate_intel_report_pdf` despatch (linhas 137-150)
- **Storage upload**: `backend/jobs/queue/jobs.py:_upload_intel_report_pdf` (linhas 158-190) — bucket `intel-reports`, signed URL TTL `INTEL_REPORT_SIGNED_URL_TTL_SECONDS`
- **Email delivery**: `backend/email_service.py:send_intel_report_ready` + template `panorama_t1_delivery.py`
- **RPC backing**: [`07-intel-report-sector-uf.md`](./07-intel-report-sector-uf.md)
- **Product surface**: [`13-intel-reports.spec.md`](./13-intel-reports.spec.md) §Endpoints + §Status State Machine

## Dependencies

- `reportlab` (SimpleDocTemplate, Platypus, Paragraph, Table, TableStyle, HRFlowable, PageBreak, Spacer)
- `backend/sectors.py:get_sector` (resolve keywords + label) — ver `backend/sectors_data.yaml`
- RPC `sector_uf_intel` (gating de dados — ver companion spec)
- `supabase_client.get_supabase()` (service_role) — passado via parâmetro `db`
- Caller orchestrator: ARQ worker `PROCESS_TYPE=worker` (Railway worker service)

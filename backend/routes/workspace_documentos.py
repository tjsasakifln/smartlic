"""Workspace Documentos routes (B2GOPS-013 / #2023).

CRUD for user-owned collaborative documents + template listing + variable
substitution from edital data in pncp_raw_bids.

Endpoints (all except /templates require auth):
  - GET    /v1/workspace/templates         — List all built-in templates
  - GET    /v1/workspace/documentos        — List user's documents (paginated)
  - POST   /v1/workspace/documentos        — Create document (optionally from template)
  - GET    /v1/workspace/documentos/{id}   — Get single document
  - PATCH  /v1/workspace/documentos/{id}   — Update document title/content
  - DELETE /v1/workspace/documentos/{id}   — Delete document
  - POST   /v1/workspace/documentos/{id}/render — Re-render variables from edital
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from auth import require_auth
from log_sanitizer import mask_user_id
from supabase_client import get_supabase, sb_execute
from schemas.workspace_documentos import (
    DocumentoCreate,
    DocumentoListResponse,
    DocumentoResponse,
    DocumentoUpdate,
    RenderDocumentoRequest,
    TemplateResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["workspace-documentos"])

# Pattern for {{variavel}} substitution
_VAR_PATTERN = re.compile(r"\{\{(\w+)\}\}")

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 200

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _row_to_template_response(row: dict) -> TemplateResponse:
    """Convert a Supabase template row to a TemplateResponse."""
    return TemplateResponse(
        id=row["id"],
        nome=row["nome"],
        tipo=row["tipo"],
        descricao=row.get("descricao"),
        conteudo=row["conteudo"],
        created_at=row["created_at"],
    )


def _row_to_documento_response(row: dict) -> DocumentoResponse:
    """Convert a Supabase document row to a DocumentoResponse."""
    return DocumentoResponse(
        id=row["id"],
        user_id=row["user_id"],
        edital_id=row.get("edital_id"),
        template_id=row.get("template_id"),
        titulo=row["titulo"],
        conteudo=row.get("conteudo") or "",
        tipo=row["tipo"],
        variaveis=row.get("variaveis") or {},
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _substituir_variaveis(
    conteudo: str,
    dados_edital: Optional[dict] = None,
    perfil: Optional[dict] = None,
) -> str:
    """Replace {{variavel}} patterns in conteudo with actual values.

    Supports variables from:
      - dados_edital: fields from pncp_raw_bids
      - perfil: user profile fields (nome, cnpj)
    Unknown patterns are left unchanged.
    """

    def _replacer(match: re.Match) -> str:
        var = match.group(1)

        # Edital variables
        if dados_edital:
            if var == "objeto":
                return dados_edital.get("objeto_compra") or dados_edital.get("objeto", "")
            if var == "orgao":
                return dados_edital.get("orgao_razao_social") or dados_edital.get("orgao", "")
            if var == "valor":
                raw = dados_edital.get("valor_total_estimado") or dados_edital.get("valor_estimado")
                if raw is not None:
                    try:
                        # Brazilian Real format: R$ 1.234,56
                        val = float(raw)
                        formatted = f"{val:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
                        return f"R$ {formatted}"
                    except (ValueError, TypeError):
                        return str(raw)
            if var == "data_abertura":
                raw = dados_edital.get("data_abertura")
                if raw:
                    try:
                        dt = datetime.fromisoformat(str(raw))
                        return dt.strftime("%d/%m/%Y")
                    except (ValueError, TypeError):
                        return str(raw)[:10]
            if var == "modalidade":
                return dados_edital.get("modalidade_nome") or dados_edital.get("modalidade", "")
            if var == "uf":
                return dados_edital.get("uf", "")

        # Profile variables
        if perfil:
            if var == "empresa":
                return perfil.get("nome") or perfil.get("full_name") or "Sua Empresa"
            if var == "cnpj":
                return perfil.get("cnpj") or "00.000.000/0000-00"

        # Unknown — leave as-is
        return match.group(0)

    return _VAR_PATTERN.sub(_replacer, conteudo)


# ---------------------------------------------------------------------------
# Templates (public read for authenticated users)
# ---------------------------------------------------------------------------


@router.get(
    "/workspace/templates",
    response_model=list[TemplateResponse],
    summary="Listar templates de documentos",
)
async def list_templates(
    user: dict = Depends(require_auth),
) -> list[TemplateResponse]:
    """List all built-in document templates.

    Templates are read-only and available to all authenticated users.
    """
    _ = user
    sb = get_supabase()

    try:
        result = await sb_execute(
            sb.table("workspace_documento_templates")
            .select("*")
            .order("nome")
        )
        return [_row_to_template_response(row) for row in (result.data or [])]
    except Exception as e:
        logger.error("Error listing templates: %s", e)
        raise HTTPException(status_code=500, detail="Erro ao listar templates.")


# ---------------------------------------------------------------------------
# Document CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/workspace/documentos",
    response_model=DocumentoListResponse,
    summary="Listar documentos do usuário",
)
async def list_documentos(
    tipo: Optional[str] = Query(None, description="Filter by document type"),
    edital_id: Optional[str] = Query(None, description="Filter by edital ID"),
    limit: int = Query(_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    user: dict = Depends(require_auth),
) -> DocumentoListResponse:
    """List the current user's documents with optional filters."""
    user_id = user["id"]
    sb = get_supabase()

    try:
        query = (
            sb.table("workspace_documentos")
            .select("*", count="exact")
            .eq("user_id", user_id)
        )

        if tipo:
            query = query.eq("tipo", tipo)
        if edital_id:
            query = query.eq("edital_id", edital_id)

        result = await sb_execute(
            query.order("updated_at", desc=True).range(offset, offset + limit - 1)
        )

        documentos = [_row_to_documento_response(row) for row in (result.data or [])]
        total = result.count if result.count is not None else len(documentos)

        return DocumentoListResponse(documentos=documentos, total=total)

    except Exception as e:
        logger.error("Error listing documentos for user %s: %s", mask_user_id(user_id), e)
        raise HTTPException(status_code=500, detail="Erro ao listar documentos.")


@router.post(
    "/workspace/documentos",
    response_model=DocumentoResponse,
    status_code=201,
    summary="Criar novo documento",
)
async def create_documento(
    body: DocumentoCreate,
    user: dict = Depends(require_auth),
) -> DocumentoResponse:
    """Create a new document for the current user.

    If template_id is provided, copies the template content into the new document.
    If edital_id is provided, pre-populates variaveis from pncp_raw_bids data.
    """
    user_id = user["id"]
    sb = get_supabase()

    try:
        conteudo = ""
        template_id = body.template_id

        # If template_id is provided, copy template content
        if template_id:
            template_result = await sb_execute(
                sb.table("workspace_documento_templates")
                .select("conteudo")
                .eq("id", template_id)
                .maybe_single()
            )
            if template_result.data:
                conteudo = template_result.data["conteudo"]

        # Build initial variaveis from edital if provided
        variaveis: dict = {}
        if body.edital_id:
            try:
                edital_result = await sb_execute(
                    sb.table("pncp_raw_bids")
                    .select("*")
                    .eq("pncp_id", body.edital_id)
                    .maybe_single()
                )
                if edital_result.data:
                    edital = edital_result.data
                    variaveis = {
                        "objeto": edital.get("objeto_compra", ""),
                        "orgao": edital.get("orgao_razao_social", ""),
                        "modalidade": edital.get("modalidade_nome", ""),
                        "valor": str(edital.get("valor_total_estimado", "")),
                        "data_abertura": str(edital.get("data_abertura", ""))[:10],
                        "uf": edital.get("uf", ""),
                    }
            except Exception:
                logger.warning(
                    "Failed to fetch edital %s for variaveis (continuing)",
                    body.edital_id,
                )

        now = datetime.now(timezone.utc).isoformat()
        insert_data = {
            "user_id": user_id,
            "titulo": body.titulo,
            "tipo": body.tipo,
            "conteudo": conteudo,
            "variaveis": variaveis,
            "created_at": now,
            "updated_at": now,
        }
        if body.edital_id:
            insert_data["edital_id"] = body.edital_id
        if body.template_id:
            insert_data["template_id"] = body.template_id

        result = await sb_execute(
            sb.table("workspace_documentos")
            .insert(insert_data)
            .select("*")
            .single()
        )

        if not result.data:
            raise HTTPException(status_code=500, detail="Erro ao criar documento.")

        logger.info("Documento created for user %s (tipo=%s)", mask_user_id(user_id), body.tipo)
        return _row_to_documento_response(result.data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error creating documento for user %s: %s", mask_user_id(user_id), e)
        raise HTTPException(status_code=500, detail="Erro ao criar documento.")


@router.get(
    "/workspace/documentos/{documento_id}",
    response_model=DocumentoResponse,
    summary="Obter documento por ID",
)
async def get_documento(
    documento_id: str,
    user: dict = Depends(require_auth),
) -> DocumentoResponse:
    """Get a single document by ID (must be owned by the current user)."""
    user_id = user["id"]
    sb = get_supabase()

    try:
        result = await sb_execute(
            sb.table("workspace_documentos")
            .select("*")
            .eq("id", documento_id)
            .eq("user_id", user_id)
            .maybe_single()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Documento nao encontrado.")

        return _row_to_documento_response(result.data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error fetching documento %s for user %s: %s",
            documento_id[:8], mask_user_id(user_id), e,
        )
        raise HTTPException(status_code=500, detail="Erro ao buscar documento.")


@router.patch(
    "/workspace/documentos/{documento_id}",
    response_model=DocumentoResponse,
    summary="Atualizar documento",
)
async def update_documento(
    documento_id: str,
    body: DocumentoUpdate,
    user: dict = Depends(require_auth),
) -> DocumentoResponse:
    """Update document title and/or content (must be owned by the current user)."""
    user_id = user["id"]
    sb = get_supabase()

    try:
        update_data: dict = {"updated_at": datetime.now(timezone.utc).isoformat()}
        if body.titulo is not None:
            update_data["titulo"] = body.titulo
        if body.conteudo is not None:
            update_data["conteudo"] = body.conteudo

        if len(update_data) <= 1:
            raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")

        result = await sb_execute(
            sb.table("workspace_documentos")
            .update(update_data)
            .eq("id", documento_id)
            .eq("user_id", user_id)
            .select("*")
            .single()
        )

        if not result.data:
            raise HTTPException(status_code=404, detail="Documento nao encontrado.")

        logger.info(
            "Documento %s updated for user %s",
            documento_id[:8], mask_user_id(user_id),
        )
        return _row_to_documento_response(result.data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error updating documento %s for user %s: %s",
            documento_id[:8], mask_user_id(user_id), e,
        )
        raise HTTPException(status_code=500, detail="Erro ao atualizar documento.")


@router.delete(
    "/workspace/documentos/{documento_id}",
    response_model=dict,
    summary="Excluir documento",
)
async def delete_documento(
    documento_id: str,
    user: dict = Depends(require_auth),
) -> dict:
    """Delete a document by ID (must be owned by the current user)."""
    user_id = user["id"]
    sb = get_supabase()

    try:
        result = await sb_execute(
            sb.table("workspace_documentos")
            .delete()
            .eq("id", documento_id)
            .eq("user_id", user_id)
        )

        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Documento nao encontrado.")

        logger.info(
            "Documento %s deleted for user %s",
            documento_id[:8], mask_user_id(user_id),
        )
        return {"success": True, "message": "Documento removido com sucesso."}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error deleting documento %s for user %s: %s",
            documento_id[:8], mask_user_id(user_id), e,
        )
        raise HTTPException(status_code=500, detail="Erro ao remover documento.")


# ---------------------------------------------------------------------------
# Render — variable substitution from edital
# ---------------------------------------------------------------------------


@router.post(
    "/workspace/documentos/{documento_id}/render",
    response_model=DocumentoResponse,
    summary="Renderizar variáveis do documento",
)
async def render_documento(
    documento_id: str,
    body: RenderDocumentoRequest,
    user: dict = Depends(require_auth),
) -> DocumentoResponse:
    """Re-render document variables from edital data.

    Fetches the edital from pncp_raw_bids and substitutes {{variavel}}
    patterns in the document content using the fetched data plus user profile.
    The updated content is saved to the document.
    """
    user_id = user["id"]
    sb = get_supabase()

    try:
        # 1. Fetch the document to verify ownership and get current content
        doc_result = await sb_execute(
            sb.table("workspace_documentos")
            .select("*")
            .eq("id", documento_id)
            .eq("user_id", user_id)
            .maybe_single()
        )

        if not doc_result.data:
            raise HTTPException(status_code=404, detail="Documento nao encontrado.")

        documento = doc_result.data
        conteudo = documento.get("conteudo") or ""

        # 2. Fetch edital data from pncp_raw_bids
        edital_data: Optional[dict] = None
        try:
            edital_result = await sb_execute(
                sb.table("pncp_raw_bids")
                .select("*")
                .eq("pncp_id", body.edital_id)
                .maybe_single()
            )
            edital_data = edital_result.data
        except Exception as e:
            logger.warning(
                "Failed to fetch edital %s for render: %s",
                body.edital_id, e,
            )

        # 3. Fetch user profile for empresa/cnpj variables
        perfil: Optional[dict] = None
        try:
            perfil_result = await sb_execute(
                sb.table("profiles")
                .select("nome, full_name, cnpj")
                .eq("id", user_id)
                .maybe_single()
            )
            perfil = perfil_result.data
        except Exception as e:
            logger.warning(
                "Failed to fetch profile for render user %s: %s",
                mask_user_id(user_id), e,
            )

        # 4. Substitute variables
        novo_conteudo = _substituir_variaveis(conteudo, edital_data, perfil)

        # 5. Save the rendered content back
        now = datetime.now(timezone.utc).isoformat()
        result = await sb_execute(
            sb.table("workspace_documentos")
            .update({
                "conteudo": novo_conteudo,
                "edital_id": body.edital_id,
                "updated_at": now,
            })
            .eq("id", documento_id)
            .eq("user_id", user_id)
            .select("*")
            .single()
        )

        if not result.data:
            raise HTTPException(status_code=500, detail="Erro ao renderizar documento.")

        logger.info(
            "Documento %s rendered for user %s",
            documento_id[:8], mask_user_id(user_id),
        )
        return _row_to_documento_response(result.data)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error rendering documento %s for user %s: %s",
            documento_id[:8], mask_user_id(user_id), e,
        )
        raise HTTPException(status_code=500, detail="Erro ao renderizar documento.")

"""Issue #1872: Public OpenAPI schema endpoint.

Serves a filtered, public OpenAPI 3.1 schema at /api/openapi.json and
/api/v1/openapi.json that:

- Excludes admin routes (/v1/admin/*)
- Sanitizes examples to avoid leaking real user data
- Sets Cache-Control: public, max-age=3600
- Uses APP_VERSION for info.version

The internal /openapi.json (FastAPI built-in, behind DOCS_ACCESS_TOKEN)
remains available for internal/admin use with the full schema.
"""

import json
import logging
import os
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["openapi"])

APP_VERSION = os.getenv("APP_VERSION", "dev")

# Cache control: schema changes rarely (only on deploy).
_CACHE_MAX_AGE = 3600  # 1 hour

# Patterns for detecting potentially sensitive example values.
# These are checked against example strings in schema properties.
_SENSITIVE_PATTERNS: list[re.Pattern] = [
    re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$"),       # email
    re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$"),       # CPF
    re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$"), # CNPJ
    re.compile(r"^\(\d{2}\)\s?\d{4,5}-\d{4}$"),       # phone
    re.compile(r"^\+55\s?\d{2}\s?\d{4,5}-\d{4}$"),    # phone with country
]

# Schema names that are likely to carry user data.
_USER_DATA_SCHEMAS = frozenset({
    "UserProfile", "Profile", "UserResponse", "UserCreate",
    "BillingInfo", "Subscription", "UserSettings",
})


def _sanitize_examples(schema: dict) -> dict:
    """Remove or sanitize examples that could leak real user data.

    Iterates through all component schemas and their properties,
    clearing any example value that matches known sensitive patterns
    (email, CPF, CNPJ, phone) or belongs to a user-data schema.

    Operates in-place on a copy of the schema dict.
    """
    components = schema.get("components", {})
    schemas = components.get("schemas", {})

    for schema_name, schema_obj in schemas.items():
        if not isinstance(schema_obj, dict):
            continue
        properties = schema_obj.get("properties", {})
        if not isinstance(properties, dict):
            continue

        for prop_name, prop_obj in properties.items():
            if not isinstance(prop_obj, dict):
                continue
            example = prop_obj.get("example")
            if example is None:
                continue
            # Clean example if it matches a sensitive pattern
            # or belongs to a user-data schema.
            if _is_sensitive_example(str(example)):
                logger.debug(
                    "Removed example from %s.%s (sensitive pattern detected)",
                    schema_name, prop_name,
                )
                del prop_obj["example"]
                continue
            # If this is a user-data schema, clear all examples for safety.
            if schema_name in _USER_DATA_SCHEMAS:
                logger.debug(
                    "Removed example from %s.%s (user-data schema)",
                    schema_name, prop_name,
                )
                del prop_obj["example"]

    return schema


def _is_sensitive_example(value: str) -> bool:
    """Check if a string value looks like sensitive data."""
    return any(pattern.match(value) for pattern in _SENSITIVE_PATTERNS)


def _filter_admin_paths(schema: dict) -> dict:
    """Remove all paths that start with /v1/admin/ from the schema.

    Operates in-place on a copy of the schema dict.
    """
    paths = schema.get("paths", {})
    admin_paths = [p for p in paths if p.startswith("/v1/admin/")]
    for p in admin_paths:
        logger.debug("Filtering admin path from public schema: %s", p)
        del paths[p]
    return schema


def _set_version(schema: dict) -> dict:
    """Set info.version to APP_VERSION."""
    info = schema.get("info", {})
    info["version"] = APP_VERSION
    return schema


def _build_public_schema(schema: dict) -> dict:
    """Apply all filters and sanitization to produce the public schema.

    Operates on a deep copy to avoid mutating the original.
    """
    public = json.loads(json.dumps(schema))  # deep copy via serialization
    public = _set_version(public)
    public = _filter_admin_paths(public)
    public = _sanitize_examples(public)
    return public


@router.get("/api/openapi.json")
async def get_public_openapi(request: Request):
    """Return filtered public OpenAPI 3.1 schema.

    Excludes admin routes (/v1/admin/*) and sanitizes examples
    to prevent leaking real user data.

    Cache-Control: public, max-age=3600 (schema changes only on deploy).
    """
    app = request.app
    # Reset schema cache so we always regenerate fresh.
    app.openapi_schema = None
    full_schema = app.openapi()
    public_schema = _build_public_schema(full_schema)

    return JSONResponse(
        content=public_schema,
        headers={
            "Cache-Control": f"public, max-age={_CACHE_MAX_AGE}",
        },
    )


@router.get("/api/v1/openapi.json")
async def get_public_openapi_v1(request: Request):
    """Versioned alias: /api/v1/openapi.json.

    Same schema as /api/openapi.json, provided for API versioning
    consistency.
    """
    return await get_public_openapi(request)

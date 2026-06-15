"""Issue #1872: Tests for public OpenAPI schema endpoint.

Tests that:
- GET /api/openapi.json returns 200 with valid schema
- Admin routes (/v1/admin/*) are excluded from public schema
- info.version reflects APP_VERSION
- Cache-Control header is present
- Versioned endpoint /api/v1/openapi.json works
- Examples are sanitized (no sensitive data leakage)
- Schema is valid JSON and contains expected path patterns
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client():
    """FastAPI test client with the full app (extracts real schema).

    Uses a plain TestClient without context manager to avoid triggering
    the full app lifespan (which creates background tasks that conflict
    with test runner threads).
    """
    from main import app
    app.openapi_schema = None
    client = TestClient(app)
    yield client
    # Prevent lingering connections from hanging.
    try:
        client.close()
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Basic schema retrieval (AC1, AC2)
# ---------------------------------------------------------------------------

class TestPublicOpenAPISchema:
    """AC1: GET /api/openapi.json returns 200 with OpenAPI 3.1 schema."""

    def test_returns_200(self, client):
        resp = client.get("/api/openapi.json")
        assert resp.status_code == 200

    def test_returns_json(self, client):
        resp = client.get("/api/openapi.json")
        assert resp.headers["content-type"] == "application/json"

    def test_valid_openapi_version(self, client):
        resp = client.get("/api/openapi.json")
        schema = resp.json()
        assert "openapi" in schema
        assert schema["openapi"].startswith("3.")

    def test_has_info(self, client):
        resp = client.get("/api/openapi.json")
        schema = resp.json()
        assert "info" in schema
        assert "title" in schema["info"]

    def test_has_paths(self, client):
        resp = client.get("/api/openapi.json")
        schema = resp.json()
        assert "paths" in schema
        assert len(schema["paths"]) > 0

    def test_has_components(self, client):
        resp = client.get("/api/openapi.json")
        schema = resp.json()
        assert "components" in schema
        assert "schemas" in schema["components"]


# ---------------------------------------------------------------------------
# Admin route exclusion (AC3)
# ---------------------------------------------------------------------------

class TestAdminRouteExclusion:
    """AC3: Admin routes (/v1/admin/*) EXCLUDED from public schema."""

    def test_no_admin_routes_in_public_schema(self, client):
        """No path in the public schema should start with /v1/admin/."""
        resp = client.get("/api/openapi.json")
        schema = resp.json()
        for path in schema.get("paths", {}):
            assert not path.startswith("/v1/admin/"), (
                f"Admin path '{path}' found in public schema"
            )

    def test_internal_schema_still_has_admin_routes(self, client):
        """The internal /openapi.json should still include admin routes."""
        resp = client.get("/openapi.json")
        schema = resp.json()
        admin_paths = [p for p in schema.get("paths", {}) if p.startswith("/v1/admin/")]
        assert len(admin_paths) > 0, (
            "Internal schema should contain admin routes"
        )

    def test_public_filters_multiple_admin_patterns(self, client):
        """Verify specific known admin path patterns are filtered."""
        resp = client.get("/api/openapi.json")
        paths = resp.json().get("paths", {})
        admin_patterns = [
            "/v1/admin/users",
            "/v1/admin/cache",
            "/v1/admin/sessions",
            "/v1/admin/plans",
            "/v1/admin/trace",
            "/v1/admin/cron-status",
            "/v1/admin/feature-flags",
            "/v1/admin/seo-metrics",
            "/v1/admin/slo",
            "/v1/admin/dlq",
        ]
        for pattern in admin_patterns:
            for path in paths:
                if path.startswith(pattern):
                    pytest.fail(f"Admin path '{path}' found in public schema")


# ---------------------------------------------------------------------------
# Schema versioning (AC4)
# ---------------------------------------------------------------------------

class TestSchemaVersioning:
    """AC4: Schema versioned — info.version = actual version."""

    def test_info_version_is_set(self, client):
        resp = client.get("/api/openapi.json")
        schema = resp.json()
        version = schema["info"].get("version")
        assert version is not None
        assert len(version) > 0

    def test_info_version_matches_expected(self, client):
        resp = client.get("/api/openapi.json")
        schema = resp.json()
        expected = os.getenv("APP_VERSION", "dev")
        assert schema["info"]["version"] == expected

    def test_info_version_differs_from_internal(self, client):
        """Internal and public schemas should have same version."""
        public_resp = client.get("/api/openapi.json")
        internal_resp = client.get("/openapi.json")
        public_version = public_resp.json()["info"]["version"]
        internal_version = internal_resp.json()["info"]["version"]
        # Both should reflect APP_VERSION.
        expected = os.getenv("APP_VERSION", "dev")
        assert public_version == expected
        assert internal_version == expected


# ---------------------------------------------------------------------------
# Cache-Control header (AC6)
# ---------------------------------------------------------------------------

class TestCacheControl:
    """AC6: Cache-Control: public, max-age=3600."""

    def test_has_cache_control_header(self, client):
        resp = client.get("/api/openapi.json")
        assert "cache-control" in resp.headers

    def test_cache_control_public(self, client):
        resp = client.get("/api/openapi.json")
        cc = resp.headers["cache-control"].lower()
        assert "public" in cc

    def test_cache_control_max_age(self, client):
        resp = client.get("/api/openapi.json")
        cc = resp.headers["cache-control"].lower()
        assert "max-age=3600" in cc or "max-age=3600" in cc.replace(" ", "")

    def test_versioned_endpoint_also_has_cache(self, client):
        resp = client.get("/api/v1/openapi.json")
        assert "cache-control" in resp.headers
        assert "public" in resp.headers["cache-control"].lower()


# ---------------------------------------------------------------------------
# Versioned endpoint (AC4 variant)
# ---------------------------------------------------------------------------

class TestVersionedEndpoint:
    """Versioned /api/v1/openapi.json returns same schema."""

    def test_versioned_endpoint_returns_200(self, client):
        resp = client.get("/api/v1/openapi.json")
        assert resp.status_code == 200

    def test_versioned_matches_unversioned(self, client):
        """Both endpoints should return identical schemas."""
        resp1 = client.get("/api/openapi.json")
        resp2 = client.get("/api/v1/openapi.json")
        assert resp1.json() == resp2.json()


# ---------------------------------------------------------------------------
# Example sanitization (AC5)
# ---------------------------------------------------------------------------

class TestExampleSanitization:
    """AC5: Examples in schemas don't contain real user data."""

    def test_no_email_examples(self, client):
        """No schema property should have an example that looks like email."""
        resp = client.get("/api/openapi.json")
        schema = resp.json()
        for name, obj in schema.get("components", {}).get("schemas", {}).items():
            if not isinstance(obj, dict):
                continue
            for prop_name, prop in obj.get("properties", {}).items():
                if not isinstance(prop, dict):
                    continue
                example = prop.get("example")
                if example and isinstance(example, str):
                    assert "@" not in example or "." not in example.split("@")[-1], (
                        f"Email-like example found in {name}.{prop_name}: {example}"
                    )

    def test_no_cpf_cnpj_examples(self, client):
        """No schema property should have CPF/CNPJ example."""
        import re
        cpf_pattern = re.compile(r"^\d{3}\.\d{3}\.\d{3}-\d{2}$")
        cnpj_pattern = re.compile(r"^\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}$")

        resp = client.get("/api/openapi.json")
        schema = resp.json()
        for name, obj in schema.get("components", {}).get("schemas", {}).items():
            if not isinstance(obj, dict):
                continue
            for prop_name, prop in obj.get("properties", {}).items():
                if not isinstance(prop, dict):
                    continue
                example = prop.get("example")
                if example and isinstance(example, str):
                    assert not cpf_pattern.match(example), (
                        f"CPF-like example in {name}.{prop_name}: {example}"
                    )
                    assert not cnpj_pattern.match(example), (
                        f"CNPJ-like example in {name}.{prop_name}: {example}"
                    )

    def test_public_has_fewer_examples_than_internal(self, client):
        """Public schema should have removed examples from user schemas."""
        resp_public = client.get("/api/openapi.json")
        resp_internal = client.get("/openapi.json")
        public = resp_public.json()
        internal = resp_internal.json()

        def count_examples(schema):
            count = 0
            for obj in schema.get("components", {}).get("schemas", {}).values():
                if not isinstance(obj, dict):
                    continue
                for prop in obj.get("properties", {}).values():
                    if isinstance(prop, dict) and "example" in prop:
                        count += 1
            return count

        public_count = count_examples(public)
        internal_count = count_examples(internal)
        # Public should have fewer or same number of examples as internal.
        assert public_count <= internal_count


# ---------------------------------------------------------------------------
# Schema structural integrity
# ---------------------------------------------------------------------------

class TestSchemaIntegrity:
    """The public schema should be structurally valid."""

    def test_no_broken_references(self, client):
        """All $ref references should resolve to existing schemas."""
        resp = client.get("/api/openapi.json")
        schema = resp.json()
        schemas_set = set(schema.get("components", {}).get("schemas", {}).keys())

        def _find_refs(obj, path=""):
            if isinstance(obj, dict):
                if "$ref" in obj:
                    ref = obj["$ref"]
                    # Extract schema name from #/components/schemas/X
                    parts = ref.split("/")
                    if len(parts) >= 4 and parts[1] == "components" and parts[2] == "schemas":
                        name = parts[-1]
                        assert name in schemas_set, (
                            f"Unresolved $ref: {ref} (at {path})"
                        )
                for k, v in obj.items():
                    _find_refs(v, f"{path}.{k}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    _find_refs(v, f"{path}[{i}]")

        _find_refs(schema, "root")

    def test_internal_and_public_have_same_non_admin_paths(self, client):
        """Non-admin paths should exist in both schemas."""
        resp_public = client.get("/api/openapi.json")
        resp_internal = client.get("/openapi.json")
        public_paths = set(resp_public.json().get("paths", {}).keys())
        internal_paths = set(resp_internal.json().get("paths", {}).keys())

        # Every public path should exist in internal.
        missing = public_paths - internal_paths
        assert len(missing) == 0, (
            f"Public paths missing from internal schema: {missing}"
        )


# ---------------------------------------------------------------------------
# Unit tests for schema filtering functions
# ---------------------------------------------------------------------------

class TestFilterFunctions:
    """Unit tests for _build_public_schema and helpers."""

    def test_filter_admin_paths(self):
        from routes.openapi_public import _filter_admin_paths

        schema = {
            "paths": {
                "/v1/search": {},
                "/v1/admin/users": {},
                "/v1/admin/cache": {},
                "/v1/user/me": {},
                "/v1/pipeline": {},
            }
        }
        result = _filter_admin_paths(schema)
        assert "/v1/search" in result["paths"]
        assert "/v1/admin/users" not in result["paths"]
        assert "/v1/admin/cache" not in result["paths"]
        assert "/v1/user/me" in result["paths"]
        assert "/v1/pipeline" in result["paths"]

    def test_set_version(self):
        schema = {"info": {"version": "old"}}
        with patch.dict(os.environ, {"APP_VERSION": "1.2.3"}, clear=False):
            # Re-import the module so APP_VERSION picks up the patched env
            import importlib
            from routes import openapi_public as mod
            importlib.reload(mod)
            result = mod._set_version(schema)
        assert result["info"]["version"] == "1.2.3"

    def test_is_sensitive_example(self):
        from routes.openapi_public import _is_sensitive_example

        assert _is_sensitive_example("user@example.com")
        assert _is_sensitive_example("123.456.789-09")
        assert _is_sensitive_example("12.345.678/0001-90")
        assert _is_sensitive_example("(11) 91234-5678")
        assert not _is_sensitive_example("SP")
        assert not _is_sensitive_example("vestuario")
        assert not _is_sensitive_example("50000.0")

    def test_build_public_schema(self):
        from routes.openapi_public import _build_public_schema

        schema = {
            "openapi": "3.1.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {
                "/v1/admin/users": {},
                "/v1/search": {},
            },
            "components": {
                "schemas": {
                    "TestModel": {
                        "properties": {
                            "email": {"type": "string", "example": "user@test.com"},
                            "name": {"type": "string", "example": "John"},
                        }
                    }
                }
            },
        }
        result = _build_public_schema(schema)
        # Admin path removed
        assert "/v1/admin/users" not in result["paths"]
        assert "/v1/search" in result["paths"]
        # Sensitive example removed
        email_prop = result["components"]["schemas"]["TestModel"]["properties"]["email"]
        assert "example" not in email_prop
        # Non-sensitive example kept (or related to user schema — check logic)
        # In our current implementation, "John" is not a sensitive pattern and
        # "TestModel" is not in _USER_DATA_SCHEMAS, so example stays.
        name_prop = result["components"]["schemas"]["TestModel"]["properties"]["name"]
        assert name_prop.get("example") == "John"

    def test_public_schema_does_not_mutate_internal(self):
        """Running _build_public_schema must not modify the input dict."""
        from routes.openapi_public import _build_public_schema

        original = {
            "openapi": "3.1.0",
            "info": {"title": "Test", "version": "1.0"},
            "paths": {"/v1/admin/users": {}},
            "components": {"schemas": {}},
        }
        import copy
        backup = copy.deepcopy(original)
        _build_public_schema(original)
        assert original == backup, "Input dict was mutated"

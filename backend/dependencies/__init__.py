"""FastAPI dependency callables shared across route modules.

RBAC-ORG-001 introduces this package to host `org_auth.require_org_role`,
a factory that returns a FastAPI dependency enforcing organization-level
RBAC (owner | member | viewer).
"""

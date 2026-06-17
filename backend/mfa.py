"""MFA Enforcement Policy — SmartLic (#1882).

Formal policy definition module for Multi-Factor Authentication enforcement
rules. This module defines the MFA policy as structured data so that routes,
middleware, and documentation can reference a single source of truth.

The actual enforcement middleware (``require_mfa``, ``require_mfa_high_impact``)
lives in ``auth.py``. This module provides the policy definition layer on top.

Policy Summary
--------------
- Admin/master roles: MFA obrigatorio (enforced at login + all routes).
- Consultoria plan: MFA obrigatorio (14-day grace window on enrollment).
- Usuarios normais: MFA opcional (recomendado, nunca bloqueado).
- Acoes sensiveis: Requerem MFA independente do plano/role.
- Recovery codes: 10 codigos, uso unico, regeneracao invalida anteriores.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ─── Policy Enums ─────────────────────────────────────────────────────────────


class MFARequirement(Enum):
    """Enforcement level for a given role/plan/action."""

    REQUIRED = "required"       # MFA is mandatory; non-enrolled users are blocked
    STEP_UP = "step_up"         # MFA required if enrolled (aal2 challenge)
    OPTIONAL = "optional"       # MFA available but never enforced
    NOT_APPLICABLE = "n/a"      # Not applicable (e.g., public endpoints)


class EnforcementReason(str, Enum):
    """Machine-readable reasons for MFA enforcement (mirrors X-MFA-Reason header)."""

    ADMIN = "admin"
    CONSULTORIA = "consultoria"
    BRUTEFORCE = "bruteforce"
    SENSITIVE_ACTION = "sensitive_action"


# ─── Policy Constants ─────────────────────────────────────────────────────────

RECOVERY_CODE_COUNT: int = 10
"""Number of recovery codes generated per enrollment. One-time use."""

RECOVERY_CODE_LENGTH: int = 8
"""Entropy of each code in hex chars (4 bytes = 2^32 possibilities)."""

SENSITIVE_ACTIONS: list[str] = [
    "delete_account",
    "change_password",
    "billing_portal",
    "subscription_cancel",
    "subscription_update_billing",
    "upgrade_to_lifetime",
]
"""Acoes sensiveis que requerem MFA independente do plano (AC1)."""

MFA_REQUIRED_PLANS: list[str] = [
    "consultoria",
]
"""Planos que exigem MFA obrigatorio (AC1)."""

MFA_REQUIRED_ROLES: list[str] = [
    "admin",
    "master",
]
"""Roles que exigem MFA obrigatorio (AC1)."""

CONSULTORIA_GRACE_DAYS: int = 14
"""Periodo de carencia para consultoria users se adequarem a politica MFA."""

BRUTEFORCE_GRACE_DAYS: int = 3
"""Periodo de carencia apos trigger de bruteforce."""


# ─── Policy Data ──────────────────────────────────────────────────────────────


@dataclass
class MFAPolicyRule:
    """A single MFA policy rule."""

    name: str
    applies_to: str  # plan, role, or action
    value: str
    requirement: MFARequirement
    reason: EnforcementReason | None = None
    grace_days: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "applies_to": self.applies_to,
            "value": self.value,
            "requirement": self.requirement.value,
            "reason": self.reason.value if self.reason else None,
            "grace_days": self.grace_days,
        }


@dataclass
class MFAPolicy:
    """Complete MFA enforcement policy as structured data.

    This is the single source of truth for MFA policy decisions.
    All enforcement logic in ``auth.py`` should reflect these rules.
    """

    version: str = "1.0"
    description: str = "SmartLic MFA Enforcement Policy"

    # ── Rules by role ─────────────────────────────────────────────────────
    role_rules: list[MFAPolicyRule] = field(default_factory=lambda: [
        MFAPolicyRule(
            name="Admin MFA required",
            applies_to="role",
            value="admin",
            requirement=MFARequirement.REQUIRED,
            reason=EnforcementReason.ADMIN,
        ),
        MFAPolicyRule(
            name="Master MFA required",
            applies_to="role",
            value="master",
            requirement=MFARequirement.REQUIRED,
            reason=EnforcementReason.ADMIN,
        ),
    ])

    # ── Rules by plan ─────────────────────────────────────────────────────
    plan_rules: list[MFAPolicyRule] = field(default_factory=lambda: [
        MFAPolicyRule(
            name="Consultoria MFA required",
            applies_to="plan",
            value="consultoria",
            requirement=MFARequirement.REQUIRED,
            reason=EnforcementReason.CONSULTORIA,
            grace_days=CONSULTORIA_GRACE_DAYS,
        ),
    ])

    # ── Rules for sensitive actions ───────────────────────────────────────
    sensitive_action_rules: list[MFAPolicyRule] = field(default_factory=lambda: [
        MFAPolicyRule(
            name="Delete account requires MFA",
            applies_to="action",
            value="delete_account",
            requirement=MFARequirement.REQUIRED,
            reason=EnforcementReason.SENSITIVE_ACTION,
        ),
        MFAPolicyRule(
            name="Change password requires MFA",
            applies_to="action",
            value="change_password",
            requirement=MFARequirement.REQUIRED,
            reason=EnforcementReason.SENSITIVE_ACTION,
        ),
        MFAPolicyRule(
            name="Billing portal requires MFA",
            applies_to="action",
            value="billing_portal",
            requirement=MFARequirement.REQUIRED,
            reason=EnforcementReason.SENSITIVE_ACTION,
        ),
        MFAPolicyRule(
            name="Subscription cancel requires MFA",
            applies_to="action",
            value="subscription_cancel",
            requirement=MFARequirement.REQUIRED,
            reason=EnforcementReason.SENSITIVE_ACTION,
        ),
        MFAPolicyRule(
            name="Subscription billing update requires MFA",
            applies_to="action",
            value="subscription_update_billing",
            requirement=MFARequirement.REQUIRED,
            reason=EnforcementReason.SENSITIVE_ACTION,
        ),
        MFAPolicyRule(
            name="Upgrade to lifetime requires MFA",
            applies_to="action",
            value="upgrade_to_lifetime",
            requirement=MFARequirement.REQUIRED,
            reason=EnforcementReason.SENSITIVE_ACTION,
        ),
    ])

    # ── Rules for regular users ───────────────────────────────────────────
    regular_user_rule: MFAPolicyRule = field(default_factory=lambda: MFAPolicyRule(
        name="Regular user MFA optional",
        applies_to="user",
        value="regular",
        requirement=MFARequirement.OPTIONAL,
    ))

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "description": self.description,
            "role_rules": [r.to_dict() for r in self.role_rules],
            "plan_rules": [r.to_dict() for r in self.plan_rules],
            "sensitive_action_rules": [r.to_dict() for r in self.sensitive_action_rules],
            "regular_user_rule": self.regular_user_rule.to_dict(),
            "recovery_code_count": RECOVERY_CODE_COUNT,
            "sensitive_actions": SENSITIVE_ACTIONS,
            "mfa_required_plans": MFA_REQUIRED_PLANS,
            "mfa_required_roles": MFA_REQUIRED_ROLES,
        }


# ─── Singleton policy instance ────────────────────────────────────────────────

_POLICY: MFAPolicy | None = None


def get_mfa_policy() -> MFAPolicy:
    """Return the singleton MFA policy instance.

    The policy is immutable by design: changing enforcement rules requires
    a code change (and review), not a runtime toggle.
    """
    global _POLICY
    if _POLICY is None:
        _POLICY = MFAPolicy()
    return _POLICY


def get_sensitive_actions() -> list[str]:
    """Return the list of sensitive actions that require MFA."""
    return list(SENSITIVE_ACTIONS)


def is_mfa_required_for_plan(plan_type: str | None) -> bool:
    """Check whether the given plan requires MFA (AC1)."""
    return plan_type in MFA_REQUIRED_PLANS if plan_type else False


def is_mfa_required_for_role(is_admin: bool, is_master: bool) -> bool:
    """Check whether the given role requires MFA (AC1)."""
    return is_admin or is_master


def is_sensitive_action(action: str) -> bool:
    """Check whether an action is classified as sensitive (AC1)."""
    return action in SENSITIVE_ACTIONS

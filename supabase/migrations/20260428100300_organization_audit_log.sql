-- RBAC-ORG-001 (AC8/AC9): organization_audit_log
--
-- Append-only event log capturing every privileged mutation an org owner
-- performs. Required for SOC2 / LGPD audit trails and for the
-- GET /v1/organizations/{id}/audit-log endpoint.
--
-- Story: docs/stories/2026-04/RBAC-ORG-001-enforce-org-role-dependency.story.md
-- ADR:   docs/adr/ADR-RBAC-ORG-001-enterprise-standard.md
--
-- Supabase CLI runs each migration file in its own transaction; no explicit
-- BEGIN/COMMIT needed (matches majority repo convention).

-- ---------------------------------------------------------------------------
-- Table
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.organization_audit_log (
  id              UUID         NOT NULL DEFAULT gen_random_uuid() PRIMARY KEY,
  org_id          UUID         NOT NULL REFERENCES public.organizations(id) ON DELETE CASCADE,
  actor_user_id   UUID         NOT NULL REFERENCES auth.users(id)            ON DELETE RESTRICT,
  target_user_id  UUID         REFERENCES auth.users(id)                     ON DELETE SET NULL,
  action          TEXT         NOT NULL,
  old_value       TEXT,
  new_value       TEXT,
  metadata        JSONB        NOT NULL DEFAULT '{}'::jsonb,
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

  CONSTRAINT organization_audit_log_action_chk
    CHECK (action IN (
      'invite_sent',
      'invite_accepted',
      'member_removed',
      'member_left',
      'role_changed',
      'transfer_ownership',
      'org_updated',
      'org_deleted',
      'logo_updated'
    ))
);

COMMENT ON TABLE  public.organization_audit_log IS 'RBAC-ORG-001 AC8: append-only audit trail of org-level mutations';
COMMENT ON COLUMN public.organization_audit_log.action      IS 'Discriminator — see CHECK constraint for allowed values';
COMMENT ON COLUMN public.organization_audit_log.old_value   IS 'Previous value (e.g. role before change). May be NULL for invite_sent.';
COMMENT ON COLUMN public.organization_audit_log.new_value   IS 'New value (e.g. role after change). May be NULL for invite_accepted.';
COMMENT ON COLUMN public.organization_audit_log.metadata    IS 'Free-form JSONB: email, IP, user-agent, etc.';

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_org_audit_log_org_created
  ON public.organization_audit_log(org_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_org_audit_log_actor
  ON public.organization_audit_log(actor_user_id);

-- ---------------------------------------------------------------------------
-- Row Level Security — owner-only SELECT, service-role full
-- ---------------------------------------------------------------------------

ALTER TABLE public.organization_audit_log ENABLE ROW LEVEL SECURITY;

-- Only the org's accepted owner can read the audit log.
DROP POLICY IF EXISTS "Org owner can read audit log" ON public.organization_audit_log;
CREATE POLICY "Org owner can read audit log"
  ON public.organization_audit_log
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
       WHERE om.org_id      = public.organization_audit_log.org_id
         AND om.user_id     = auth.uid()
         AND om.role        = 'owner'
         AND om.accepted_at IS NOT NULL
    )
  );

-- Service-role (backend) full access — append-only writes happen here.
DROP POLICY IF EXISTS "Service role full access on org audit log" ON public.organization_audit_log;
CREATE POLICY "Service role full access on org audit log"
  ON public.organization_audit_log
  FOR ALL
  USING (auth.role() = 'service_role');

-- Explicitly forbid any UPDATE / DELETE through normal grants — audit
-- log rows are immutable. The `service_role` policy above still allows
-- backend writes via Supabase service-role client; if you ever need to
-- redact a row, do it via a SECURITY DEFINER function with explicit
-- justification logged.
REVOKE UPDATE, DELETE ON public.organization_audit_log FROM authenticated;
REVOKE UPDATE, DELETE ON public.organization_audit_log FROM anon;

-- ---------------------------------------------------------------------------
-- Grants
-- ---------------------------------------------------------------------------

GRANT SELECT, INSERT ON public.organization_audit_log TO authenticated;
GRANT ALL            ON public.organization_audit_log TO service_role;

-- ---------------------------------------------------------------------------
-- Verification
-- ---------------------------------------------------------------------------

DO $$
BEGIN
  RAISE NOTICE 'RBAC-ORG-001 AC8: organization_audit_log table created';
END $$;

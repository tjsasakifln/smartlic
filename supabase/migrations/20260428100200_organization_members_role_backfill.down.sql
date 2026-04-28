-- RBAC-ORG-001 ROLLBACK: revert organization_members role enum + RLS policies
--
-- IDEMPOTENCY: every step uses IF EXISTS / DROP-and-recreate so this can
-- run safely on a partially-applied state.
--
-- DATA NOTE: rolling back does NOT restore individual members that used
-- to be 'admin' — that information was destructively rewritten to
-- 'member' by the up migration. The down script keeps them as 'member';
-- if you genuinely need to recover the pre-migration mapping, restore
-- from a database snapshot taken before 2026-04-28.

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Drop the new CHECK constraint
-- ---------------------------------------------------------------------------
ALTER TABLE public.organization_members
  DROP CONSTRAINT IF EXISTS organization_members_role_check;

-- ---------------------------------------------------------------------------
-- 2. Reinstate the legacy CHECK constraint (owner | admin | member).
--    Existing 'viewer' rows would violate this, so we first downgrade
--    them to 'member' (closest legacy semantics — viewer was read-only,
--    legacy 'member' was also non-admin).
-- ---------------------------------------------------------------------------
UPDATE public.organization_members
   SET role = 'member'
 WHERE role = 'viewer';

ALTER TABLE public.organization_members
  ADD CONSTRAINT organization_members_role_check
  CHECK (role IN ('owner', 'admin', 'member'));

COMMENT ON COLUMN public.organization_members.role IS
  'Role within the org: owner (full control), admin (manage members), member (read-only team access)';

-- ---------------------------------------------------------------------------
-- 3. Restore legacy RLS policies referencing the 'admin' role.
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS "Org members can view organization"      ON public.organizations;
DROP POLICY IF EXISTS "Org members can view all members"       ON public.organization_members;
DROP POLICY IF EXISTS "Org owner can insert members"           ON public.organization_members;
DROP POLICY IF EXISTS "Org owner or self can delete members"   ON public.organization_members;

CREATE POLICY "Org admins can view organization"
  ON public.organizations
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
       WHERE om.org_id  = public.organizations.id
         AND om.user_id = auth.uid()
         AND om.role    IN ('owner', 'admin')
         AND om.accepted_at IS NOT NULL
    )
  );

CREATE POLICY "Org owner/admin can view all members"
  ON public.organization_members
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
       WHERE om.org_id  = public.organization_members.org_id
         AND om.user_id = auth.uid()
         AND om.role    IN ('owner', 'admin')
         AND om.accepted_at IS NOT NULL
    )
  );

CREATE POLICY "Org owner/admin can insert members"
  ON public.organization_members
  FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.organization_members om
       WHERE om.org_id  = public.organization_members.org_id
         AND om.user_id = auth.uid()
         AND om.role    IN ('owner', 'admin')
         AND om.accepted_at IS NOT NULL
    )
    OR
    EXISTS (
      SELECT 1 FROM public.organizations o
       WHERE o.id       = public.organization_members.org_id
         AND o.owner_id = auth.uid()
    )
  );

CREATE POLICY "Org owner/admin can delete members"
  ON public.organization_members
  FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
       WHERE om.org_id  = public.organization_members.org_id
         AND om.user_id = auth.uid()
         AND om.role    IN ('owner', 'admin')
         AND om.accepted_at IS NOT NULL
    )
    OR
    auth.uid() = user_id
  );

COMMIT;

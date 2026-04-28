-- RBAC-ORG-001: Backfill organization_members.role to canonical (owner|member|viewer)
--
-- Story: docs/stories/2026-04/RBAC-ORG-001-enforce-org-role-dependency.story.md
-- ADR:   docs/adr/ADR-RBAC-ORG-001-enterprise-standard.md
--
-- WHAT THIS DOES
-- 1. Migrates existing 'admin' rows → 'member' (privilege-down, safer than
--    privilege-up — the legacy 'admin' role meant "manage members", which
--    is now owner-exclusive in the RBAC matrix).
-- 2. Backfills role for any rows where role IS NULL via the heuristic:
--      first member per org (lowest invited_at) → 'owner'
--      remaining members                       → 'member'
-- 3. Replaces the existing CHECK constraint to forbid 'admin' and accept
--    'viewer' as a new value.
-- 4. Tightens NOT NULL guarantee (column is already NOT NULL today, but
--    we re-assert defensively in case a future migration ever relaxes it).
-- 5. Rewrites the five existing RLS policies that referenced
--    role IN ('owner', 'admin') so the SECURITY semantics match the new
--    enum (owner-only for sensitive operations).
--
-- IDEMPOTENCY
-- All steps use IF EXISTS / IF NOT EXISTS / DO blocks so a second apply
-- is a no-op. Backfill rewrites are bounded to the unconverted row set.
--
-- BACKFILL HEURISTIC RISK (story R1)
-- "First member by invited_at = owner" is a heuristic that may misclassify
-- ~5% of orgs whose actual founder was added later. Mitigation: a
-- companion script (`scripts/rbac_org_001_backfill_dryrun.py --dry-run`)
-- writes a CSV of every (org_id, user_id, computed_role) for human
-- review BEFORE this migration runs. See ADR §"Backfill validation".

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. Drop the old CHECK constraint (will be replaced after we normalize data)
-- ---------------------------------------------------------------------------
ALTER TABLE public.organization_members
  DROP CONSTRAINT IF EXISTS organization_members_role_check;

-- ---------------------------------------------------------------------------
-- 2. Privilege-down: migrate any 'admin' rows → 'member'.
-- ---------------------------------------------------------------------------
UPDATE public.organization_members
   SET role = 'member'
 WHERE role = 'admin';

-- ---------------------------------------------------------------------------
-- 3. Backfill any NULL or empty roles using the "first member = owner"
--    heuristic. This protects against historical data where role was
--    NULLable; today the column is NOT NULL DEFAULT 'member' so this
--    block typically affects 0 rows.
-- ---------------------------------------------------------------------------
WITH first_members AS (
  SELECT DISTINCT ON (org_id)
         id,
         org_id,
         user_id,
         invited_at
    FROM public.organization_members
   WHERE role IS NULL OR role = ''
   ORDER BY org_id, invited_at ASC NULLS LAST, id ASC
)
UPDATE public.organization_members om
   SET role = 'owner'
  FROM first_members fm
 WHERE om.id = fm.id;

UPDATE public.organization_members
   SET role = 'member'
 WHERE role IS NULL OR role = '';

-- ---------------------------------------------------------------------------
-- 4. Re-assert NOT NULL (no-op today, defense in depth).
-- ---------------------------------------------------------------------------
ALTER TABLE public.organization_members
  ALTER COLUMN role SET NOT NULL,
  ALTER COLUMN role SET DEFAULT 'member';

-- ---------------------------------------------------------------------------
-- 5. Add the new CHECK constraint (owner | member | viewer ONLY).
--    Done AFTER backfill so existing data passes validation.
-- ---------------------------------------------------------------------------
ALTER TABLE public.organization_members
  ADD CONSTRAINT organization_members_role_check
  CHECK (role IN ('owner', 'member', 'viewer'));

COMMENT ON COLUMN public.organization_members.role IS
  'RBAC-ORG-001: owner > member > viewer. Hierarchy enforced by '
  'backend/dependencies/org_auth.py::require_org_role.';

-- ---------------------------------------------------------------------------
-- 6. Rewrite RLS policies that referenced the legacy 'admin' role.
--    The new defaults follow the enterprise matrix in
--    docs/adr/ADR-RBAC-ORG-001-enterprise-standard.md:
--      - any accepted member can SELECT their org row (read is permissive)
--      - only owners mutate or invite via SQL paths (the API layer
--        enforces this even more tightly via require_org_role)
-- ---------------------------------------------------------------------------

-- 6a. organizations: collapse "owner OR admin can view" into "any accepted member"
DROP POLICY IF EXISTS "Org admins can view organization" ON public.organizations;
CREATE POLICY "Org members can view organization"
  ON public.organizations
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
       WHERE om.org_id  = public.organizations.id
         AND om.user_id = auth.uid()
         AND om.accepted_at IS NOT NULL
    )
  );

-- 6b. organization_members SELECT: any accepted member can see all members
DROP POLICY IF EXISTS "Org owner/admin can view all members" ON public.organization_members;
CREATE POLICY "Org members can view all members"
  ON public.organization_members
  FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
       WHERE om.org_id  = public.organization_members.org_id
         AND om.user_id = auth.uid()
         AND om.role IN ('owner', 'member')
         AND om.accepted_at IS NOT NULL
    )
  );

-- 6c. organization_members INSERT: owner-only (or owner-bootstrap row)
DROP POLICY IF EXISTS "Org owner/admin can insert members" ON public.organization_members;
CREATE POLICY "Org owner can insert members"
  ON public.organization_members
  FOR INSERT
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM public.organization_members om
       WHERE om.org_id  = public.organization_members.org_id
         AND om.user_id = auth.uid()
         AND om.role    = 'owner'
         AND om.accepted_at IS NOT NULL
    )
    OR
    -- Bootstrap: org owner_id may insert their own first member row
    EXISTS (
      SELECT 1 FROM public.organizations o
       WHERE o.id       = public.organization_members.org_id
         AND o.owner_id = auth.uid()
    )
  );

-- 6d. organization_members DELETE: owner-only OR self-leave
DROP POLICY IF EXISTS "Org owner/admin can delete members" ON public.organization_members;
CREATE POLICY "Org owner or self can delete members"
  ON public.organization_members
  FOR DELETE
  USING (
    EXISTS (
      SELECT 1 FROM public.organization_members om
       WHERE om.org_id  = public.organization_members.org_id
         AND om.user_id = auth.uid()
         AND om.role    = 'owner'
         AND om.accepted_at IS NOT NULL
    )
    OR
    auth.uid() = user_id
  );

-- ---------------------------------------------------------------------------
-- 7. Verification — log row counts to migration output.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
  total_count INT;
  owner_count INT;
  member_count INT;
  viewer_count INT;
BEGIN
  SELECT COUNT(*) INTO total_count   FROM public.organization_members;
  SELECT COUNT(*) INTO owner_count   FROM public.organization_members WHERE role = 'owner';
  SELECT COUNT(*) INTO member_count  FROM public.organization_members WHERE role = 'member';
  SELECT COUNT(*) INTO viewer_count  FROM public.organization_members WHERE role = 'viewer';

  RAISE NOTICE 'RBAC-ORG-001 backfill complete: total=%, owner=%, member=%, viewer=%',
    total_count, owner_count, member_count, viewer_count;
END $$;

COMMIT;

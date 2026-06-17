ALTER TABLE profiles ADD COLUMN IF NOT EXISTS admin_roles text[] DEFAULT '{}';
UPDATE profiles SET admin_roles = ARRAY['admin:super'] WHERE is_admin = true AND (admin_roles IS NULL OR admin_roles = '{}' OR admin_roles = ARRAY[]::text[]);
CREATE OR REPLACE FUNCTION has_admin_role(role text) RETURNS boolean LANGUAGE sql SECURITY DEFINER STABLE AS $$ SELECT EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND (admin_roles @> ARRAY['admin:super'] OR admin_roles @> ARRAY[role])); $$;
COMMENT ON COLUMN profiles.admin_roles IS 'Granular admin roles (#1912). Values: admin:users, admin:billing, admin:cache, admin:partners, admin:seo, admin:ops, admin:compliance, admin:super';
COMMENT ON FUNCTION has_admin_role IS 'Check if current user has a specific admin role or admin:super (#1912)';

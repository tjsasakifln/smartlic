-- #1804: LGPD data deletion requests table
-- Supports double opt-out flow: request → email confirmation → soft-delete
CREATE TABLE IF NOT EXISTS public.data_deletion_requests (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  status          text NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending','confirmed','completed','cancelled')),
  requested_at    timestamptz NOT NULL DEFAULT now(),
  confirmed_at    timestamptz,
  completed_at    timestamptz,
  cancelled_at    timestamptz,
  deletion_token  text,           -- HMAC-SHA256 of raw token (constant-time verify)
  reason          text DEFAULT '',
  created_at      timestamptz NOT NULL DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_data_deletion_requests_user_id
  ON public.data_deletion_requests(user_id);
CREATE INDEX IF NOT EXISTS idx_data_deletion_requests_status
  ON public.data_deletion_requests(status);
CREATE INDEX IF NOT EXISTS idx_data_deletion_requests_token
  ON public.data_deletion_requests(deletion_token)
  WHERE deletion_token IS NOT NULL;

-- RLS enabled
ALTER TABLE public.data_deletion_requests ENABLE ROW LEVEL SECURITY;

-- Policies
DROP POLICY IF EXISTS "Service role manages all deletion requests" ON public.data_deletion_requests;
CREATE POLICY "Service role manages all deletion requests"
  ON public.data_deletion_requests
  FOR ALL
  USING (true)
  WITH CHECK (true);

DROP POLICY IF EXISTS "Users read own deletion requests" ON public.data_deletion_requests;
CREATE POLICY "Users read own deletion requests"
  ON public.data_deletion_requests
  FOR SELECT
  USING (auth.uid() = user_id);

DROP POLICY IF EXISTS "Users insert own deletion request" ON public.data_deletion_requests;
CREATE POLICY "Users insert own deletion request"
  ON public.data_deletion_requests
  FOR INSERT
  WITH CHECK (auth.uid() = user_id AND status = 'pending');

DROP POLICY IF EXISTS "Users update own pending request" ON public.data_deletion_requests;
CREATE POLICY "Users update own pending request"
  ON public.data_deletion_requests
  FOR UPDATE
  USING (auth.uid() = user_id AND status = 'pending');

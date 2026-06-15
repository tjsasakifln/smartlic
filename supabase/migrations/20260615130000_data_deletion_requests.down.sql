-- Rollback for data_deletion_requests table (#1804)
DROP POLICY IF EXISTS "Users update own pending request" ON public.data_deletion_requests;
DROP POLICY IF EXISTS "Users insert own deletion request" ON public.data_deletion_requests;
DROP POLICY IF EXISTS "Users read own deletion requests" ON public.data_deletion_requests;
DROP POLICY IF EXISTS "Service role manages all deletion requests" ON public.data_deletion_requests;
DROP INDEX IF EXISTS idx_data_deletion_requests_token;
DROP INDEX IF EXISTS idx_data_deletion_requests_status;
DROP INDEX IF EXISTS idx_data_deletion_requests_user_id;
DROP TABLE IF EXISTS public.data_deletion_requests;

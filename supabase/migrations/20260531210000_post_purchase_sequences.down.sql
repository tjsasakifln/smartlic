DROP TRIGGER IF EXISTS trg_pps_updated_at ON post_purchase_sequences;
DROP FUNCTION IF EXISTS update_pps_updated_at();
DROP TABLE IF EXISTS post_purchase_sequences CASCADE;

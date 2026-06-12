-- Rollback MKT-001: Remove subcontract marketplace tables
-- Order matters: drop dependent table first, then main table

DROP TABLE IF EXISTS subcontract_interests;
DROP TABLE IF EXISTS subcontract_opportunities;

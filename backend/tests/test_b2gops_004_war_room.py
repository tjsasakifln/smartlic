"""Tests for B2GOPS-004: workspace_war_rooms schema + RPCs + SSE channel.

Validates the migration SQL contract, RPC signatures, grants, RLS policies,
return shapes, and the B2G_OPS_ENABLED feature flag.

These tests are purely static/contract validation — they do NOT connect to
a live database. RPC behavior (ops_create_war_room, ops_add_war_room_member,
ops_log_war_room_action, ops_get_war_room, ops_toggle_checklist_item) is
validated via mock supabase.rpc() chains.
"""

from __future__ import annotations

import json
import os
import re
from unittest.mock import MagicMock, call

import pytest

from tests.conftest import mock_supabase as _mock_supabase  # noqa: F401

# Paths relative to repo root
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MIGRATIONS_DIR = os.path.join(REPO_ROOT, "supabase", "migrations")

MIGRATION_FILE = "20260602000000_workspace_war_rooms.sql"
DOWN_FILE = "20260602000000_workspace_war_rooms.down.sql"

# Expected columns for workspace_war_rooms
WAR_ROOM_COLUMNS = [
    "id", "user_id", "licitacao_id", "licitacao_fonte",
    "status", "checklist", "notas_rapidas", "created_at", "updated_at",
]

# Expected columns for workspace_war_room_members
MEMBER_COLUMNS = [
    "id", "workspace_war_room_id", "user_id", "papel",
    "ativo", "joined_at",
]

# Expected columns for workspace_war_room_log
LOG_COLUMNS = [
    "id", "war_room_id", "user_id", "acao",
    "descricao", "metadados", "created_at",
]

# Expected JSON keys from ops_create_war_room
WAR_ROOM_KEYS = [
    "id", "user_id", "licitacao_id", "licitacao_fonte",
    "status", "checklist", "notas_rapidas", "created_at", "updated_at",
]

# Expected JSON keys from ops_add_war_room_member
MEMBER_KEYS = [
    "id", "workspace_war_room_id", "user_id", "papel",
    "ativo", "joined_at",
]

# Expected JSON keys from ops_log_war_room_action
LOG_ENTRY_KEYS = [
    "id", "war_room_id", "user_id", "acao",
    "descricao", "metadados", "created_at",
]

# Valid actions for log
VALID_ACOES = [
    "checklist_toggle", "nota_adicionada", "membro_adicionado",
    "membro_removido", "status_change", "documento_adicionado",
]

# Valid papéis (roles)
VALID_PAPEIS = [
    "lider", "documentacao", "lances", "juridico", "observador", "membro",
]

# Valid statuses for war room
VALID_STATUSES = ["preparacao", "em_andamento", "concluida"]

# Feature flag name
B2G_OPS_ENABLED_FLAG = "B2G_OPS_ENABLED"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_sql(filename: str) -> str:
    path = os.path.join(MIGRATIONS_DIR, filename)
    with open(path) as f:
        return f.read()


def _build_mock_result(data: list) -> MagicMock:
    """Build a supabase RPC execute result wrapping ``data``."""
    result = MagicMock()
    result.data = data
    return result


def _rpc_execute(result_data: list | None = None, side_effect: Exception | None = None):
    """Patch helper: returns a supabase rpc() chain ending in execute()."""
    rpc_chain = MagicMock()
    if side_effect:
        rpc_chain.execute.side_effect = side_effect
    else:
        rpc_result = _build_mock_result(result_data or [])
        rpc_chain.execute.return_value = rpc_result
    return rpc_chain


# ---------------------------------------------------------------------------
# Sample data (simulates what the RPCs return)
# ---------------------------------------------------------------------------

SAMPLE_WAR_ROOM_UUID = "00000000-0000-0000-0000-000000000001"
SAMPLE_USER_UUID = "user-123-uuid"
SAMPLE_MEMBER_UUID = "user-456-uuid"

SAMPLE_WAR_ROOM_RESPONSE = {
    "id": SAMPLE_WAR_ROOM_UUID,
    "user_id": SAMPLE_USER_UUID,
    "licitacao_id": "12345",
    "licitacao_fonte": "pncp",
    "status": "preparacao",
    "checklist": [],
    "notas_rapidas": None,
    "created_at": "2026-06-02T12:00:00+00:00",
    "updated_at": "2026-06-02T12:00:00+00:00",
}

SAMPLE_MEMBER_RESPONSE = {
    "id": "00000000-0000-0000-0000-000000000010",
    "workspace_war_room_id": SAMPLE_WAR_ROOM_UUID,
    "user_id": SAMPLE_USER_UUID,
    "papel": "lider",
    "ativo": True,
    "joined_at": "2026-06-02T12:00:00+00:00",
}

SAMPLE_ADDED_MEMBER_RESPONSE = {
    "id": "00000000-0000-0000-0000-000000000011",
    "workspace_war_room_id": SAMPLE_WAR_ROOM_UUID,
    "user_id": SAMPLE_MEMBER_UUID,
    "papel": "membro",
    "ativo": True,
    "joined_at": "2026-06-02T12:00:00+00:00",
}

SAMPLE_LOG_RESPONSE = {
    "id": "00000000-0000-0000-0000-000000000020",
    "war_room_id": SAMPLE_WAR_ROOM_UUID,
    "user_id": SAMPLE_USER_UUID,
    "acao": "membro_adicionado",
    "descricao": "Membro adicionado com papel membro",
    "metadados": {"member_user_id": SAMPLE_MEMBER_UUID, "papel": "membro"},
    "created_at": "2026-06-02T12:00:00+00:00",
}

SAMPLE_CHECKLIST = [
    {"id": "item-1", "texto": "Verificar documentacao", "concluido": False, "data_conclusao": None},
    {"id": "item-2", "texto": "Analisar edital", "concluido": True, "data_conclusao": "2026-06-02T13:00:00+00:00"},
]

SAMPLE_WAR_ROOM_WITH_CHECKLIST = {
    **SAMPLE_WAR_ROOM_RESPONSE,
    "checklist": SAMPLE_CHECKLIST,
}


# ===================================================================
# Migration Contract Tests
# ===================================================================


class TestMigrationContract:
    """Validate the SQL migration files are well-formed."""

    def test_migration_file_exists(self):
        path = os.path.join(MIGRATIONS_DIR, MIGRATION_FILE)
        assert os.path.exists(path), f"Migration file not found: {path}"

    def test_down_file_exists(self):
        path = os.path.join(MIGRATIONS_DIR, DOWN_FILE)
        assert os.path.exists(path), f"Down migration not found: {path}"

    # -- Tables --

    def test_workspace_war_rooms_table_created(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CREATE TABLE workspace_war_rooms" in sql, (
            "Missing workspace_war_rooms table"
        )

    def test_workspace_war_room_members_table_created(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CREATE TABLE workspace_war_room_members" in sql, (
            "Missing workspace_war_room_members table"
        )

    def test_workspace_war_room_log_table_created(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CREATE TABLE workspace_war_room_log" in sql, (
            "Missing workspace_war_room_log table"
        )

    def test_war_room_all_columns(self):
        sql = _read_sql(MIGRATION_FILE)
        for col in WAR_ROOM_COLUMNS:
            assert col in sql, f"Missing workspace_war_rooms column: {col}"

    def test_member_all_columns(self):
        sql = _read_sql(MIGRATION_FILE)
        for col in MEMBER_COLUMNS:
            assert col in sql, f"Missing workspace_war_room_members column: {col}"

    def test_log_all_columns(self):
        sql = _read_sql(MIGRATION_FILE)
        for col in LOG_COLUMNS:
            assert col in sql, f"Missing workspace_war_room_log column: {col}"

    def test_unique_constraint_on_war_room(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "UNIQUE(user_id, licitacao_id, licitacao_fonte)" in sql, (
            "Missing UNIQUE constraint on (user_id, licitacao_id, licitacao_fonte)"
        )

    def test_unique_constraint_on_members(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "UNIQUE(workspace_war_room_id, user_id)" in sql, (
            "Missing UNIQUE constraint on (workspace_war_room_id, user_id)"
        )

    def test_war_room_status_check_constraint(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CHECK (status IN ('preparacao', 'em_andamento', 'concluida'))" in sql, (
            "Missing CHECK constraint on status"
        )

    def test_member_papel_check_constraint(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CHECK (papel IN (" in sql, "Missing CHECK constraint on papel"
        for role in VALID_PAPEIS:
            assert role in sql, f"Missing papel role: {role}"

    def test_log_acao_check_constraint(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CHECK (acao IN (" in sql, "Missing CHECK constraint on acao"
        for acao in VALID_ACOES:
            assert acao in sql, f"Missing acao: {acao}"

    def test_on_delete_cascade_war_room_user(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "REFERENCES auth.users(id) ON DELETE CASCADE" in sql, (
            "Missing ON DELETE CASCADE for user_id FK in war rooms"
        )

    def test_on_delete_cascade_member_room(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "REFERENCES workspace_war_rooms(id) ON DELETE CASCADE" in sql, (
            "Missing ON DELETE CASCADE for war_room_id FK in members"
        )

    def test_on_delete_cascade_log_room(self):
        sql = _read_sql(MIGRATION_FILE)
        count = sql.count("ON DELETE CASCADE")
        # 5 FKs total: war_rooms.user_id, members.workspace_war_room_id, members.user_id,
        #              log.war_room_id, log.user_id
        assert count == 5, (
            f"Expected 5 ON DELETE CASCADE (3 tables × user + 2 FK to war_rooms), "
            f"found {count}"
        )

    def test_indexes_created(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "idx_war_rooms_user" in sql, "Missing idx_war_rooms_user"
        assert "idx_war_rooms_licitacao" in sql, "Missing idx_war_rooms_licitacao"
        assert "idx_war_room_members_room" in sql, "Missing idx_war_room_members_room"
        assert "idx_war_room_members_user" in sql, "Missing idx_war_room_members_user"
        assert "idx_war_room_log_room" in sql, "Missing idx_war_room_log_room"
        assert "idx_war_room_log_created" in sql, "Missing idx_war_room_log_created"

    # -- RLS --

    def test_rls_enabled_on_war_rooms(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "ALTER TABLE workspace_war_rooms ENABLE ROW LEVEL SECURITY" in sql, (
            "Missing RLS enable on workspace_war_rooms"
        )

    def test_rls_enabled_on_members(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "ALTER TABLE workspace_war_room_members ENABLE ROW LEVEL SECURITY" in sql, (
            "Missing RLS enable on workspace_war_room_members"
        )

    def test_rls_enabled_on_log(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "ALTER TABLE workspace_war_room_log ENABLE ROW LEVEL SECURITY" in sql, (
            "Missing RLS enable on workspace_war_room_log"
        )

    def test_war_rooms_rls_owner_policy(self):
        sql = _read_sql(MIGRATION_FILE)
        assert 'CREATE POLICY "Owner can CRUD war room"' in sql, (
            "Missing owner CRUD policy on war rooms"
        )
        assert "auth.uid() = user_id" in sql, (
            "Owner policy must enforce auth.uid() = user_id"
        )

    def test_war_rooms_rls_member_view_policy(self):
        sql = _read_sql(MIGRATION_FILE)
        assert 'CREATE POLICY "Members can view war room"' in sql, (
            "Missing member view policy on war rooms"
        )

    def test_members_rls_owner_policy(self):
        sql = _read_sql(MIGRATION_FILE)
        assert 'CREATE POLICY "Room owner can manage members"' in sql, (
            "Missing owner manage members policy"
        )

    def test_members_rls_member_view_policy(self):
        sql = _read_sql(MIGRATION_FILE)
        assert 'CREATE POLICY "Members can view member list"' in sql, (
            "Missing member view member list policy"
        )

    def test_log_rls_view_policy(self):
        sql = _read_sql(MIGRATION_FILE)
        assert 'CREATE POLICY "Room participants can view log"' in sql, (
            "Missing participants view log policy"
        )

    def test_log_rls_insert_policy(self):
        sql = _read_sql(MIGRATION_FILE)
        assert 'CREATE POLICY "Room participants can insert log"' in sql, (
            "Missing participants insert log policy"
        )

    # -- RPC: ops_create_war_room --

    def test_ops_create_war_room_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CREATE OR REPLACE FUNCTION ops_create_war_room" in sql, (
            "Missing ops_create_war_room function"
        )

    def test_ops_create_war_room_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_licitacao_id TEXT" in sql, "Missing p_licitacao_id parameter"
        assert "p_licitacao_fonte TEXT" in sql, "Missing p_licitacao_fonte parameter"

    def test_ops_create_war_room_returns_table_type(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS workspace_war_rooms" in sql, (
            "Must return workspace_war_rooms type"
        )

    def test_ops_create_war_room_security_definer(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SECURITY DEFINER" in sql, "Missing SECURITY DEFINER"

    def test_ops_create_war_room_search_path(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SET search_path = ''" in sql, (
            "Missing search_path = ''"
        )

    def test_ops_create_war_room_uses_auth_uid(self):
        """ops_create_war_room must use auth.uid(), NOT receive user_id as param."""
        sql = _read_sql(MIGRATION_FILE)
        assert "auth.uid()" in sql, "Must use auth.uid()"
        # Scoped check: only the ops_create_war_room function block
        func_start = sql.index("ops_create_war_room(")
        func_end = sql.index("END;", func_start)
        func_body = sql[func_start:func_end]
        assert "p_user_id" not in func_body, (
            "ops_create_war_room must NOT receive user_id as parameter"
        )

    def test_ops_create_war_room_idempotent(self):
        """ops_create_war_room must use ON CONFLICT DO UPDATE."""
        sql = _read_sql(MIGRATION_FILE)
        assert "ON CONFLICT" in sql, "Must handle ON CONFLICT for idempotency"
        assert "DO UPDATE" in sql, "Must use DO UPDATE for idempotency"

    def test_ops_create_war_room_auto_adds_lider(self):
        """ops_create_war_room must auto-insert creator as lider."""
        sql = _read_sql(MIGRATION_FILE)
        assert "lider" in sql, "Must auto-add creator as lider"

    # -- RPC: ops_add_war_room_member --

    def test_ops_add_war_room_member_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CREATE OR REPLACE FUNCTION ops_add_war_room_member" in sql, (
            "Missing ops_add_war_room_member function"
        )

    def test_ops_add_war_room_member_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_war_room_id UUID" in sql, "Missing p_war_room_id parameter"
        assert "p_user_id UUID" in sql, "Missing p_user_id parameter"

    def test_ops_add_war_room_member_returns_table_type(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS workspace_war_room_members" in sql, (
            "Must return workspace_war_room_members type"
        )

    def test_ops_add_war_room_member_security_definer(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SECURITY DEFINER" in sql, "Missing SECURITY DEFINER"

    def test_ops_add_war_room_member_search_path(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SET search_path = ''" in sql, (
            "Missing search_path = ''"
        )

    def test_ops_add_war_room_member_authorization(self):
        """ops_add_war_room_member must check owner or lider role."""
        sql = _read_sql(MIGRATION_FILE)
        assert "RAISE EXCEPTION" in sql, (
            "Must raise exception for unauthorized users"
        )
        assert "Only room owner or lider" in sql, (
            "Error message must indicate role restriction"
        )

    # -- RPC: ops_log_war_room_action --

    def test_ops_log_war_room_action_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CREATE OR REPLACE FUNCTION ops_log_war_room_action" in sql, (
            "Missing ops_log_war_room_action function"
        )

    def test_ops_log_war_room_action_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_war_room_id UUID" in sql, "Missing p_war_room_id parameter"
        assert "p_acao TEXT" in sql, "Missing p_acao parameter"
        assert "p_descricao TEXT" in sql, "Missing p_descricao parameter"
        assert "p_metadados JSONB" in sql, "Missing p_metadados parameter"

    def test_ops_log_war_room_action_pg_notify(self):
        """ops_log_war_room_action must use pg_notify for SSE."""
        sql = _read_sql(MIGRATION_FILE)
        assert "pg_notify" in sql, "Missing pg_notify for SSE channel"
        assert "war_room_" in sql, "pg_notify must use war_room_ prefix channel"

    def test_ops_log_war_room_action_returns_table_type(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS workspace_war_room_log" in sql, (
            "Must return workspace_war_room_log type"
        )

    def test_ops_log_war_room_action_security_definer(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SECURITY DEFINER" in sql, "Missing SECURITY DEFINER"

    def test_ops_log_war_room_action_search_path(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SET search_path = ''" in sql, (
            "Missing search_path = ''"
        )

    # -- RPC: ops_get_war_room --

    def test_ops_get_war_room_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CREATE OR REPLACE FUNCTION ops_get_war_room" in sql, (
            "Missing ops_get_war_room function"
        )

    def test_ops_get_war_room_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_licitacao_id TEXT" in sql, "Missing p_licitacao_id parameter"
        assert "p_licitacao_fonte TEXT" in sql, "Missing p_licitacao_fonte parameter"

    def test_ops_get_war_room_returns_setof(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS SETOF workspace_war_rooms" in sql, (
            "Must return SETOF workspace_war_rooms"
        )

    def test_ops_get_war_room_member_visibility(self):
        """ops_get_war_room must include member war rooms."""
        sql = _read_sql(MIGRATION_FILE)
        assert "workspace_war_room_members" in sql, (
            "Must join workspace_war_room_members for visibility"
        )

    # -- RPC: ops_toggle_checklist_item --

    def test_ops_toggle_checklist_item_function(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "CREATE OR REPLACE FUNCTION ops_toggle_checklist_item" in sql, (
            "Missing ops_toggle_checklist_item function"
        )

    def test_ops_toggle_checklist_item_params(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "p_war_room_id UUID" in sql, "Missing p_war_room_id parameter"
        assert "p_item_id TEXT" in sql, "Missing p_item_id parameter"
        assert "p_concluido BOOLEAN" in sql, "Missing p_concluido parameter"

    def test_ops_toggle_checklist_item_returns_table_type(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "RETURNS workspace_war_rooms" in sql, (
            "Must return workspace_war_rooms type"
        )

    def test_ops_toggle_checklist_item_security_definer(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SECURITY DEFINER" in sql, "Missing SECURITY DEFINER"

    def test_ops_toggle_checklist_item_search_path(self):
        sql = _read_sql(MIGRATION_FILE)
        assert "SET search_path = ''" in sql, (
            "Missing search_path = ''"
        )

    def test_ops_toggle_checklist_item_jsonb_manipulation(self):
        """ops_toggle_checklist_item must manipulate JSONB checklist array."""
        sql = _read_sql(MIGRATION_FILE)
        assert "jsonb_set" in sql, "Must use jsonb_set to update checklist"
        assert "jsonb_array_length" in sql, (
            "Must iterate over jsonb_array_length"
        )

    def test_ops_toggle_checklist_item_logs_action(self):
        """ops_toggle_checklist_item must log the toggle action."""
        sql = _read_sql(MIGRATION_FILE)
        assert "checklist_toggle" in sql, (
            "Must log checklist_toggle action"
        )

    # -- Down migration --

    def test_down_drops_functions(self):
        sql = _read_sql(DOWN_FILE)
        assert "DROP FUNCTION IF EXISTS ops_toggle_checklist_item" in sql, (
            "Down must drop ops_toggle_checklist_item"
        )
        assert "DROP FUNCTION IF EXISTS ops_get_war_room" in sql, (
            "Down must drop ops_get_war_room"
        )
        assert "DROP FUNCTION IF EXISTS ops_log_war_room_action" in sql, (
            "Down must drop ops_log_war_room_action"
        )
        assert "DROP FUNCTION IF EXISTS ops_add_war_room_member" in sql, (
            "Down must drop ops_add_war_room_member"
        )
        assert "DROP FUNCTION IF EXISTS ops_create_war_room" in sql, (
            "Down must drop ops_create_war_room"
        )

    def test_down_drops_tables(self):
        sql = _read_sql(DOWN_FILE)
        assert "DROP TABLE IF EXISTS workspace_war_room_log" in sql, (
            "Down must drop workspace_war_room_log"
        )
        assert "DROP TABLE IF EXISTS workspace_war_room_members" in sql, (
            "Down must drop workspace_war_room_members"
        )
        assert "DROP TABLE IF EXISTS workspace_war_rooms" in sql, (
            "Down must drop workspace_war_rooms"
        )

    def test_down_drops_policies(self):
        sql = _read_sql(DOWN_FILE)
        assert 'DROP POLICY IF EXISTS "Room participants can insert log"' in sql, (
            "Down must drop log insert policy"
        )
        assert 'DROP POLICY IF EXISTS "Room participants can view log"' in sql, (
            "Down must drop log view policy"
        )
        assert 'DROP POLICY IF EXISTS "Members can view member list"' in sql, (
            "Down must drop member list policy"
        )
        assert 'DROP POLICY IF EXISTS "Room owner can manage members"' in sql, (
            "Down must drop manage members policy"
        )
        assert 'DROP POLICY IF EXISTS "Members can view war room"' in sql, (
            "Down must drop member view policy"
        )
        assert 'DROP POLICY IF EXISTS "Owner can CRUD war room"' in sql, (
            "Down must drop owner CRUD policy"
        )

    def test_no_existing_objects_altered(self):
        """Ensure migration doesn't alter any existing tables or RPCs."""
        sql = _read_sql(MIGRATION_FILE)
        # Count CREATE OR REPLACE FUNCTION occurrences
        func_count = len(re.findall(r"CREATE OR REPLACE FUNCTION", sql))
        assert func_count == 5, (
            f"Expected exactly 5 CREATE OR REPLACE FUNCTION, found {func_count}"
        )
        # Count CREATE TABLE occurrences
        table_count = len(re.findall(r"CREATE TABLE workspace_", sql))
        assert table_count == 3, (
            f"Expected exactly 3 CREATE TABLE, found {table_count}"
        )


# ===================================================================
# Return Shape Tests
# ===================================================================


class TestReturnShape:
    """Validate the RPC JSON shapes against the specification."""

    def test_war_room_all_expected_keys(self):
        for key in WAR_ROOM_KEYS:
            assert key in SAMPLE_WAR_ROOM_RESPONSE, f"Missing key: {key}"

    def test_war_room_no_extra_keys(self):
        extra = set(SAMPLE_WAR_ROOM_RESPONSE.keys()) - set(WAR_ROOM_KEYS)
        assert not extra, f"Unexpected keys: {extra}"

    def test_war_room_uuid_fields(self):
        assert isinstance(SAMPLE_WAR_ROOM_RESPONSE["id"], str)
        assert isinstance(SAMPLE_WAR_ROOM_RESPONSE["user_id"], str)

    def test_war_room_string_fields(self):
        for key in ("licitacao_id", "licitacao_fonte", "status"):
            assert isinstance(SAMPLE_WAR_ROOM_RESPONSE[key], str), (
                f"{key} must be str, got {type(SAMPLE_WAR_ROOM_RESPONSE[key])}"
            )

    def test_war_room_jsonb_field(self):
        assert isinstance(SAMPLE_WAR_ROOM_RESPONSE["checklist"], list), (
            "checklist must be a list"
        )

    def test_war_room_timestamp_fields(self):
        for key in ("created_at", "updated_at"):
            assert isinstance(SAMPLE_WAR_ROOM_RESPONSE[key], str), (
                f"{key} must be str (ISO timestamp)"
            )

    def test_member_all_expected_keys(self):
        for key in MEMBER_KEYS:
            assert key in SAMPLE_MEMBER_RESPONSE, f"Missing key: {key}"

    def test_member_no_extra_keys(self):
        extra = set(SAMPLE_MEMBER_RESPONSE.keys()) - set(MEMBER_KEYS)
        assert not extra, f"Unexpected keys: {extra}"

    def test_member_types(self):
        assert isinstance(SAMPLE_MEMBER_RESPONSE["papel"], str)
        assert isinstance(SAMPLE_MEMBER_RESPONSE["ativo"], bool)

    def test_log_all_expected_keys(self):
        for key in LOG_ENTRY_KEYS:
            assert key in SAMPLE_LOG_RESPONSE, f"Missing key: {key}"

    def test_log_no_extra_keys(self):
        extra = set(SAMPLE_LOG_RESPONSE.keys()) - set(LOG_ENTRY_KEYS)
        assert not extra, f"Unexpected keys: {extra}"

    def test_log_types(self):
        assert isinstance(SAMPLE_LOG_RESPONSE["acao"], str)
        assert isinstance(SAMPLE_LOG_RESPONSE["descricao"], str)
        assert isinstance(SAMPLE_LOG_RESPONSE["metadados"], dict)

    def test_checklist_item_structure(self):
        item = SAMPLE_CHECKLIST[0]
        assert "id" in item
        assert "texto" in item
        assert "concluido" in item
        assert "data_conclusao" in item
        assert isinstance(item["concluido"], bool)


# ===================================================================
# Supabase RPC Mock Integration Tests
# ===================================================================


class TestSupabaseRPCIntegration:
    """Validate that supabase.rpc() can call the functions with correct params."""

    def test_ops_create_war_room_call_signature(self):
        """ops_create_war_room must accept (p_licitacao_id, p_licitacao_fonte)."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_WAR_ROOM_RESPONSE])

        mock_rpc.rpc(
            "ops_create_war_room",
            {
                "p_licitacao_id": "12345",
                "p_licitacao_fonte": "pncp",
            },
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_create_war_room",
            {
                "p_licitacao_id": "12345",
                "p_licitacao_fonte": "pncp",
            },
        )

    def test_ops_create_war_room_returns_full_row(self):
        """The RPC returns the full war room row."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_WAR_ROOM_RESPONSE])

        result = mock_rpc.rpc(
            "ops_create_war_room",
            {"p_licitacao_id": "12345", "p_licitacao_fonte": "pncp"},
        ).execute()

        resp = result.data[0]
        assert resp["licitacao_id"] == "12345"
        assert resp["licitacao_fonte"] == "pncp"
        assert resp["user_id"] == SAMPLE_USER_UUID
        assert resp["status"] == "preparacao"

    def test_ops_create_war_room_idempotent_call(self):
        """Same licitacao_id + licitacao_fonte should update updated_at."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_WAR_ROOM_RESPONSE])

        # Simulate two calls with same params
        mock_rpc.rpc(
            "ops_create_war_room",
            {"p_licitacao_id": "12345", "p_licitacao_fonte": "pncp"},
        ).execute()

        mock_rpc.rpc(
            "ops_create_war_room",
            {"p_licitacao_id": "12345", "p_licitacao_fonte": "pncp"},
        ).execute()

        assert mock_rpc.rpc.call_count == 2

    def test_ops_add_war_room_member_call_signature(self):
        """ops_add_war_room_member must accept (p_war_room_id, p_user_id[, p_papel])."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_ADDED_MEMBER_RESPONSE])

        mock_rpc.rpc(
            "ops_add_war_room_member",
            {
                "p_war_room_id": SAMPLE_WAR_ROOM_UUID,
                "p_user_id": SAMPLE_MEMBER_UUID,
                "p_papel": "membro",
            },
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_add_war_room_member",
            {
                "p_war_room_id": SAMPLE_WAR_ROOM_UUID,
                "p_user_id": SAMPLE_MEMBER_UUID,
                "p_papel": "membro",
            },
        )

    def test_ops_add_war_room_member_returns_member(self):
        """The RPC returns the member row."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_ADDED_MEMBER_RESPONSE])

        result = mock_rpc.rpc(
            "ops_add_war_room_member",
            {
                "p_war_room_id": SAMPLE_WAR_ROOM_UUID,
                "p_user_id": SAMPLE_MEMBER_UUID,
                "p_papel": "membro",
            },
        ).execute()

        resp = result.data[0]
        assert resp["workspace_war_room_id"] == SAMPLE_WAR_ROOM_UUID
        assert resp["user_id"] == SAMPLE_MEMBER_UUID
        assert resp["papel"] == "membro"
        assert resp["ativo"] is True

    def test_ops_add_war_room_member_default_papel(self):
        """Default papel should be 'membro' when not provided."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[{
            **SAMPLE_ADDED_MEMBER_RESPONSE,
            "papel": "membro",
        }])

        result = mock_rpc.rpc(
            "ops_add_war_room_member",
            {
                "p_war_room_id": SAMPLE_WAR_ROOM_UUID,
                "p_user_id": SAMPLE_MEMBER_UUID,
            },
        ).execute()

        resp = result.data[0]
        assert resp["papel"] == "membro"

    def test_ops_log_war_room_action_call_signature(self):
        """ops_log_war_room_action must accept (p_war_room_id, p_acao, p_descricao[, p_metadados])."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_LOG_RESPONSE])

        mock_rpc.rpc(
            "ops_log_war_room_action",
            {
                "p_war_room_id": SAMPLE_WAR_ROOM_UUID,
                "p_acao": "membro_adicionado",
                "p_descricao": "Membro adicionado com papel membro",
                "p_metadados": json.dumps({"member_user_id": SAMPLE_MEMBER_UUID, "papel": "membro"}),
            },
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_log_war_room_action",
            {
                "p_war_room_id": SAMPLE_WAR_ROOM_UUID,
                "p_acao": "membro_adicionado",
                "p_descricao": "Membro adicionado com papel membro",
                "p_metadados": json.dumps({"member_user_id": SAMPLE_MEMBER_UUID, "papel": "membro"}),
            },
        )

    def test_ops_log_war_room_action_returns_log(self):
        """The RPC returns the log entry row."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_LOG_RESPONSE])

        result = mock_rpc.rpc(
            "ops_log_war_room_action",
            {
                "p_war_room_id": SAMPLE_WAR_ROOM_UUID,
                "p_acao": "membro_adicionado",
                "p_descricao": "Membro adicionado com papel membro",
            },
        ).execute()

        resp = result.data[0]
        assert resp["war_room_id"] == SAMPLE_WAR_ROOM_UUID
        assert resp["acao"] == "membro_adicionado"
        assert "Membro adicionado" in resp["descricao"]

    def test_ops_get_war_room_call_signature(self):
        """ops_get_war_room must accept (p_licitacao_id, p_licitacao_fonte)."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_WAR_ROOM_RESPONSE])

        mock_rpc.rpc(
            "ops_get_war_room",
            {
                "p_licitacao_id": "12345",
                "p_licitacao_fonte": "pncp",
            },
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_get_war_room",
            {
                "p_licitacao_id": "12345",
                "p_licitacao_fonte": "pncp",
            },
        )

    def test_ops_get_war_room_returns_list(self):
        """The RPC returns a list of war rooms (SETOF)."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_WAR_ROOM_RESPONSE])

        result = mock_rpc.rpc(
            "ops_get_war_room",
            {"p_licitacao_id": "12345", "p_licitacao_fonte": "pncp"},
        ).execute()

        assert len(result.data) >= 1
        assert result.data[0]["licitacao_id"] == "12345"

    def test_ops_get_war_room_not_found(self):
        """When no war room exists, returns empty list."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[])

        result = mock_rpc.rpc(
            "ops_get_war_room",
            {"p_licitacao_id": "nonexistent", "p_licitacao_fonte": "pncp"},
        ).execute()

        assert len(result.data) == 0

    def test_ops_toggle_checklist_item_call_signature(self):
        """ops_toggle_checklist_item must accept (p_war_room_id, p_item_id, p_concluido)."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[SAMPLE_WAR_ROOM_WITH_CHECKLIST])

        mock_rpc.rpc(
            "ops_toggle_checklist_item",
            {
                "p_war_room_id": SAMPLE_WAR_ROOM_UUID,
                "p_item_id": "item-1",
                "p_concluido": True,
            },
        ).execute()

        mock_rpc.rpc.assert_called_once_with(
            "ops_toggle_checklist_item",
            {
                "p_war_room_id": SAMPLE_WAR_ROOM_UUID,
                "p_item_id": "item-1",
                "p_concluido": True,
            },
        )

    def test_ops_toggle_checklist_item_returns_war_room(self):
        """The RPC returns the updated war room row."""
        updated_war_room = {
            **SAMPLE_WAR_ROOM_RESPONSE,
            "checklist": [
                {"id": "item-1", "texto": "Verificar documentacao", "concluido": True,
                 "data_conclusao": "2026-06-02T14:00:00+00:00"},
                {"id": "item-2", "texto": "Analisar edital", "concluido": True,
                 "data_conclusao": "2026-06-02T13:00:00+00:00"},
            ],
        }
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[updated_war_room])

        result = mock_rpc.rpc(
            "ops_toggle_checklist_item",
            {
                "p_war_room_id": SAMPLE_WAR_ROOM_UUID,
                "p_item_id": "item-1",
                "p_concluido": True,
            },
        ).execute()

        resp = result.data[0]
        checklist = resp["checklist"]
        assert len(checklist) == 2
        # item-1 should now be concluido=true
        item1 = next(i for i in checklist if i["id"] == "item-1")
        assert item1["concluido"] is True
        assert item1["data_conclusao"] is not None

        # item-2 should remain concluido=true
        item2 = next(i for i in checklist if i["id"] == "item-2")
        assert item2["concluido"] is True

    def test_ops_toggle_checklist_item_uncheck(self):
        """Unchecking an item should set concluido=false and clear data_conclusao."""
        unchecked = {
            **SAMPLE_WAR_ROOM_RESPONSE,
            "checklist": [
                {"id": "item-2", "texto": "Analisar edital", "concluido": False,
                 "data_conclusao": None},
            ],
        }
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.return_value = MagicMock(data=[unchecked])

        result = mock_rpc.rpc(
            "ops_toggle_checklist_item",
            {
                "p_war_room_id": SAMPLE_WAR_ROOM_UUID,
                "p_item_id": "item-2",
                "p_concluido": False,
            },
        ).execute()

        resp = result.data[0]
        item = resp["checklist"][0]
        assert item["concluido"] is False
        assert item["data_conclusao"] is None

    def test_rpc_error_handling_create(self):
        """RPC failure should propagate the exception."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.side_effect = Exception(
            "function ops_create_war_room(text, text) does not exist"
        )

        with pytest.raises(Exception) as exc:
            mock_rpc.rpc(
                "ops_create_war_room",
                {"p_licitacao_id": "12345", "p_licitacao_fonte": "pncp"},
            ).execute()

        assert "ops_create_war_room" in str(exc.value)

    def test_rpc_error_handling_auth(self):
        """Unauthorized RPC call should propagate the exception."""
        mock_rpc = MagicMock()
        mock_rpc.rpc.return_value = mock_rpc
        mock_rpc.execute.side_effect = Exception(
            "Only room owner or lider can add members"
        )

        with pytest.raises(Exception) as exc:
            mock_rpc.rpc(
                "ops_add_war_room_member",
                {
                    "p_war_room_id": SAMPLE_WAR_ROOM_UUID,
                    "p_user_id": SAMPLE_MEMBER_UUID,
                },
            ).execute()

        assert "Only room owner or lider" in str(exc.value)

    def test_ops_create_war_room_no_user_id_param(self):
        """ops_create_war_room must NOT receive user_id as a parameter."""
        sql = _read_sql(MIGRATION_FILE)
        # Scoped check: only the ops_create_war_room function block
        func_start = sql.index("ops_create_war_room(")
        func_end = sql.index("END;", func_start)
        func_body = sql[func_start:func_end]
        assert "p_user_id" not in func_body, (
            "ops_create_war_room must not accept user_id — uses auth.uid() instead"
        )

    def test_ops_add_war_room_member_logs_action(self):
        """Adding a member should automatically log the action."""
        sql = _read_sql(MIGRATION_FILE)
        assert "membro_adicionado" in sql, (
            "ops_add_war_room_member must log membro_adicionado action"
        )
        assert "INSERT INTO workspace_war_room_log" in sql, (
            "ops_add_war_room_member must insert into workspace_war_room_log"
        )

    @pytest.mark.parametrize("key", WAR_ROOM_KEYS)
    def test_war_room_all_keys_present_in_sample(self, key):
        """Parametrized: every expected key must be present in sample response."""
        assert key in SAMPLE_WAR_ROOM_RESPONSE, f"Key '{key}' missing from sample"

    @pytest.mark.parametrize("key", MEMBER_KEYS)
    def test_member_all_keys_present_in_sample(self, key):
        """Parametrized: every expected key must be present in sample response."""
        assert key in SAMPLE_MEMBER_RESPONSE, f"Key '{key}' missing from sample"

    @pytest.mark.parametrize("key", LOG_ENTRY_KEYS)
    def test_log_all_keys_present_in_sample(self, key):
        """Parametrized: every expected key must be present in sample response."""
        assert key in SAMPLE_LOG_RESPONSE, f"Key '{key}' missing from sample"


# ===================================================================
# JSON Serialization Tests
# ===================================================================


class TestJSONSerialization:
    """Validate the RPC responses round-trip through JSON."""

    def test_war_room_response_serializable(self):
        json.dumps(SAMPLE_WAR_ROOM_RESPONSE)

    def test_member_response_serializable(self):
        json.dumps(SAMPLE_MEMBER_RESPONSE)

    def test_log_response_serializable(self):
        json.dumps(SAMPLE_LOG_RESPONSE)

    def test_war_room_json_round_trip(self):
        serialized = json.dumps(SAMPLE_WAR_ROOM_RESPONSE)
        deserialized = json.loads(serialized)
        assert deserialized == SAMPLE_WAR_ROOM_RESPONSE

    def test_member_json_round_trip(self):
        serialized = json.dumps(SAMPLE_MEMBER_RESPONSE)
        deserialized = json.loads(serialized)
        assert deserialized == SAMPLE_MEMBER_RESPONSE

    def test_log_json_round_trip(self):
        serialized = json.dumps(SAMPLE_LOG_RESPONSE)
        deserialized = json.loads(serialized)
        assert deserialized == SAMPLE_LOG_RESPONSE

    def test_checklist_json_round_trip(self):
        serialized = json.dumps(SAMPLE_CHECKLIST)
        deserialized = json.loads(serialized)
        assert deserialized == SAMPLE_CHECKLIST


# ===================================================================
# RLS Isolation Tests (Contract Level)
# ===================================================================


class TestRLSEnforcement:
    """Validate RLS policies from the SQL contract perspective."""

    def test_non_member_cannot_view_war_room(self):
        """Non-member policy must use NOT EXISTS pattern."""
        sql = _read_sql(MIGRATION_FILE)
        # The "Members can view war room" policy uses EXISTS with subquery
        assert 'CREATE POLICY "Members can view war room"' in sql
        assert "EXISTS" in sql

    def test_non_member_cannot_see_members(self):
        """Non-member cannot see member list (EXISTS check)."""
        sql = _read_sql(MIGRATION_FILE)
        assert 'CREATE POLICY "Members can view member list"' in sql
        assert "EXISTS" in sql

    def test_owner_full_access(self):
        """Owner can CRUD must be FOR ALL."""
        sql = _read_sql(MIGRATION_FILE)
        assert 'FOR ALL USING' in sql

    def test_log_entry_author_is_logged(self):
        """Log insert must enforce auth.uid() = user_id."""
        sql = _read_sql(MIGRATION_FILE)
        assert "auth.uid() = user_id" in sql, (
            "Log insert must enforce auth.uid() = user_id"
        )

    def test_log_viewable_by_participants(self):
        """Log must be viewable by room participants."""
        sql = _read_sql(MIGRATION_FILE)
        assert "Room participants can view log" in sql, (
            "Missing log view policy for participants"
        )

    def test_member_table_rls_on_manage(self):
        """Member table RLS must check room owner via subquery."""
        sql = _read_sql(MIGRATION_FILE)
        assert "Room owner can manage members" in sql


# ===================================================================
# Feature Flag Tests
# ===================================================================


class TestFeatureFlag:
    """Validate the B2G_OPS_ENABLED feature flag."""

    def test_b2g_ops_flag_defined(self):
        """B2G_OPS_ENABLED must be defined in config.features module-level."""
        from config.features import B2G_OPS_ENABLED  # noqa: F401

    def test_b2g_ops_flag_default_true(self):
        """B2G_OPS_ENABLED must default to True (active in production)."""
        from config.features import B2G_OPS_ENABLED as flag

        # When no env is set, default must be True
        assert flag is True, "B2G_OPS_ENABLED must default to True"

    def test_b2g_ops_flag_in_registry(self):
        """B2G_OPS_ENABLED must be in the runtime feature flag registry."""
        from config.features import _FEATURE_FLAG_REGISTRY

        assert "B2G_OPS_ENABLED" in _FEATURE_FLAG_REGISTRY, (
            "B2G_OPS_ENABLED missing from _FEATURE_FLAG_REGISTRY"
        )

    def test_b2g_ops_flag_registry_value(self):
        """Registry entry must have default true."""
        from config.features import _FEATURE_FLAG_REGISTRY

        env_var, registry_default = _FEATURE_FLAG_REGISTRY["B2G_OPS_ENABLED"]
        assert registry_default == "true", (
            f"Registry default must be 'true', got '{registry_default}'"
        )

    def test_b2g_ops_flag_env_override_true(self, monkeypatch):
        """Setting env var to true should return True via get_feature_flag."""
        from config.features import get_feature_flag

        monkeypatch.setenv("B2G_OPS_ENABLED", "true")
        # Clear cache to force re-read from env
        from config.features import _feature_flag_cache
        _feature_flag_cache.clear()

        assert get_feature_flag("B2G_OPS_ENABLED") is True

    def test_b2g_ops_flag_env_override_false(self, monkeypatch):
        """Setting env var to false should return False via get_feature_flag."""
        from config.features import get_feature_flag

        monkeypatch.setenv("B2G_OPS_ENABLED", "false")
        from config.features import _feature_flag_cache
        _feature_flag_cache.clear()

        assert get_feature_flag("B2G_OPS_ENABLED") is False

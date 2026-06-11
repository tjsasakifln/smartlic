"""CONV-011b-1: Tests for post_purchase_sequences.

Coverage:
- Migration static analysis: file exists with correct columns, constraints, RLS
- Webhook: checkout.session.completed mode=payment com product_sku cria sequencia
- Webhook: checkout.session.completed mode=subscription NAO cria sequencia
- Webhook: Idempotencia — mesmo purchase_id nao cria duplicata
- Webhook: Metadata faltando (sem product_sku ou user_id) trata graceful
- Webhook: Branching correto — product_sku nao conflita com product_type ou founding
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = REPO_ROOT.parent  # project root = ../ from backend/
MIGRATIONS_DIR = PROJECT_ROOT / "supabase" / "migrations"


# ─────────────────────────────────────────────────────────────────────────────
# Helpers / Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_fake_supabase(insert_data=None, select_data=None):
    """Return a mock supabase client that chains table().select/insert/eq/…/execute().

    The mock uses side_effect on execute() so that:

    - For idempotency tests (select_data=truthy): the SELECT check returns data,
      and no INSERT is attempted.
    - For insert tests (insert_data=truthy): the SELECT check returns empty
      (no existing sequence), and INSERT returns insert_data.
    - For both provided: SELECT returns select_data, INSERT returns insert_data.
    """
    sb = MagicMock()
    chain = MagicMock()

    select_result = MagicMock(data=select_data or [])
    insert_result = MagicMock(data=insert_data or [])

    # Use side_effect so first execute() (SELECT/idempotency) differs from
    # second execute() (INSERT). If no insert_data, both return select_data.
    if insert_data is not None:
        chain.execute.side_effect = [select_result, insert_result]
    elif select_data is not None:
        chain.execute.return_value = select_result
    else:
        chain.execute.return_value = MagicMock(data=[])

    for method in ("table", "select", "insert", "update", "eq", "order", "single", "limit"):
        getattr(chain, method).return_value = chain
    sb.table.return_value = chain
    return sb, chain


def _make_session_data(
    product_sku=None,
    user_id="user-test-uuid-0001",
    mode="payment",
    session_id="cs_test_postpurchase_001",
    product_type=None,
    source=None,
):
    """Build a session_data dict mimicking a Stripe checkout.session.completed object.

    Args:
        product_sku: SKU do produto digital (ex: 'relatorio-oportunidade')
        user_id: ID do usuario
        mode: 'payment' para one-time, 'subscription' para assinatura
        session_id: ID da sessao Stripe
        product_type: Se presente, simula Intel Report (#630)
        source: Se 'founding', simula founding checkout
    """
    metadata = {}
    if product_sku:
        metadata["product_sku"] = product_sku
    if user_id:
        metadata["user_id"] = user_id
    if product_type:
        metadata["product_type"] = product_type
    if source:
        metadata["source"] = source

    data = {
        "id": session_id,
        "mode": mode,
        "metadata": metadata,
    }

    obj = MagicMock()
    obj.get = lambda key, default=None: data.get(key, default)
    obj.__getitem__ = lambda self_, key: data[key]
    obj.__contains__ = lambda self_, key: key in data
    return obj


def _make_checkout_event(session_data):
    """Build a mock stripe.Event wrapping session_data."""
    event = MagicMock()
    event.data = MagicMock()
    event.data.object = session_data
    return event


# ─────────────────────────────────────────────────────────────────────────────
# 1. Migration static analysis
# ─────────────────────────────────────────────────────────────────────────────

class TestMigrationFile:
    """Static analysis of the migration SQL file."""

    def _find_migration(self):
        """Find the post_purchase_sequences migration file.

        Sorts by filename descending so the newest migration is always
        selected deterministically (Path.glob() order is filesystem-dependent).
        """
        pattern = "*post_purchase_sequences.sql"
        matches = list(MIGRATIONS_DIR.glob(pattern))
        # Exclude .down.sql
        matches = [m for m in matches if not m.name.endswith(".down.sql")]
        # Sort by filename descending → newest timestamp first
        matches.sort(key=lambda p: p.name, reverse=True)
        return matches[0] if matches else None

    def test_migration_file_exists(self):
        migration = self._find_migration()
        assert migration is not None, (
            "Migration file post_purchase_sequences.sql not found in "
            f"{MIGRATIONS_DIR}"
        )

    def test_down_migration_exists(self):
        migration = self._find_migration()
        assert migration is not None
        down_path = migration.with_suffix(".down.sql")
        assert down_path.exists(), (
            f"Paired down.sql not found at {down_path}"
        )

    def test_migration_creates_table(self):
        migration = self._find_migration()
        assert migration is not None
        content = migration.read_text()
        assert "CREATE TABLE public.post_purchase_sequences" in content

    def test_migration_has_status_check_constraint(self):
        migration = self._find_migration()
        assert migration is not None
        content = migration.read_text()
        assert "CHECK (status IN (" in content
        assert "pending" in content
        assert "active" in content
        assert "completed" in content
        assert "cancelled" in content

    def test_migration_has_rls_policies(self):
        migration = self._find_migration()
        assert migration is not None
        content = migration.read_text()
        assert "ENABLE ROW LEVEL SECURITY" in content
        assert "GRANT ALL ON public.post_purchase_sequences TO service_role" in content
        assert "GRANT SELECT ON public.post_purchase_sequences TO authenticated" in content
        assert "USING (auth.uid() = user_id)" in content

    def test_migration_has_indexes(self):
        migration = self._find_migration()
        assert migration is not None
        content = migration.read_text()
        assert "idx_post_purchase_purchase" in content
        assert "idx_post_purchase_user_status" in content

    def test_migration_has_updated_at_trigger(self):
        migration = self._find_migration()
        assert migration is not None
        content = migration.read_text()
        assert "set_post_purchase_sequences_updated_at" in content
        assert "trg_post_purchase_sequences_updated_at" in content

    def test_migration_has_required_columns(self):
        migration = self._find_migration()
        assert migration is not None
        content = migration.read_text()
        required = [
            "purchase_id",
            "product_sku",
            "user_id",
            "status",
            "sequence_steps",
            "current_step",
            "created_at",
            "updated_at",
        ]
        for col in required:
            assert col in content, f"Missing required column: {col}"

    def test_down_migration_drops_table(self):
        migration = self._find_migration()
        assert migration is not None
        down_path = migration.with_suffix(".down.sql")
        content = down_path.read_text()
        assert "DROP TABLE IF EXISTS public.post_purchase_sequences" in content

    def test_down_migration_drops_trigger_and_function(self):
        migration = self._find_migration()
        assert migration is not None
        down_path = migration.with_suffix(".down.sql")
        content = down_path.read_text()
        assert "DROP TRIGGER IF EXISTS trg_post_purchase_sequences_updated_at" in content
        assert "DROP FUNCTION IF EXISTS public.set_post_purchase_sequences_updated_at" in content


# ─────────────────────────────────────────────────────────────────────────────
# 2. Webhook: handle_digital_product_checkout_completed
# ─────────────────────────────────────────────────────────────────────────────

class TestDigitalProductWebhookHandler:
    """Tests for handle_digital_product_checkout_completed."""

    @pytest.mark.asyncio
    async def test_inserts_sequence_row(self):
        """mode=payment com product_sku deve criar sequencia."""
        sb, chain = _make_fake_supabase(insert_data=[{"id": "seq-uuid-001"}])
        session_data = _make_session_data(product_sku="relatorio-oportunidade")

        with patch("job_queue.get_arq_pool", side_effect=Exception("no arq pool")):
            from webhooks.handlers.checkout import handle_digital_product_checkout_completed
            await handle_digital_product_checkout_completed(sb, session_data)

        # Assert .table("post_purchase_sequences").insert(...).execute() was called
        sb.table.assert_called_with("post_purchase_sequences")
        chain.insert.assert_called_once()
        insert_arg = chain.insert.call_args[0][0]
        assert insert_arg["purchase_id"] == "cs_test_postpurchase_001"
        assert insert_arg["product_sku"] == "relatorio-oportunidade"
        assert insert_arg["user_id"] == "user-test-uuid-0001"
        assert insert_arg["stage"] == "delivery"
        assert insert_arg["next_sequence_at"] is not None
        chain.execute.assert_called()

    @pytest.mark.asyncio
    async def test_missing_product_sku_skips_insert(self):
        """Sem product_sku no metadata, handler deve logar warning e retornar sem inserir."""
        sb, chain = _make_fake_supabase()
        session_data = _make_session_data(product_sku=None)

        from webhooks.handlers.checkout import handle_digital_product_checkout_completed
        await handle_digital_product_checkout_completed(sb, session_data)

        chain.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_user_id_skips_insert(self):
        """Sem user_id no metadata, handler deve logar warning e retornar sem inserir."""
        sb, chain = _make_fake_supabase()
        session_data = _make_session_data(product_sku="relatorio-oportunidade", user_id=None)

        from webhooks.handlers.checkout import handle_digital_product_checkout_completed
        await handle_digital_product_checkout_completed(sb, session_data)

        chain.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_empty_metadata_skips_insert(self):
        """Metadata vazio nao deve causar erro — apenas log e retorno."""
        sb, chain = _make_fake_supabase()
        session_data = _make_session_data(product_sku=None, user_id=None)

        from webhooks.handlers.checkout import handle_digital_product_checkout_completed
        await handle_digital_product_checkout_completed(sb, session_data)

        chain.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_idempotency_existing_sequence_skips_insert(self):
        """Se purchase_id ja existe em post_purchase_sequences, nao deve criar duplicata."""
        sb, chain = _make_fake_supabase(
            select_data=[{"id": "existing-seq", "stage": "delivery"}]
        )
        session_data = _make_session_data(product_sku="relatorio-oportunidade")

        from webhooks.handlers.checkout import handle_digital_product_checkout_completed
        await handle_digital_product_checkout_completed(sb, session_data)

        # insert nao deve ser chamado porque a sequencia ja existe
        chain.insert.assert_not_called()

    @pytest.mark.asyncio
    async def test_arq_failure_does_not_raise(self):
        """Falha no ARQ (best-effort) nao deve propagar excecao."""
        sb, chain = _make_fake_supabase(insert_data=[{"id": "seq-uuid-001"}])
        session_data = _make_session_data(product_sku="relatorio-oportunidade")

        with patch("job_queue.get_arq_pool", side_effect=Exception("ARQ pool unavailable")):
            from webhooks.handlers.checkout import handle_digital_product_checkout_completed
            await handle_digital_product_checkout_completed(sb, session_data)

        # Purchase row was still inserted
        chain.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_enqueues_followup_and_reengagement_jobs(self):
        """Quando ARQ disponivel, deve enfileirar jobs de followup e reengagement."""
        mock_pool = AsyncMock()
        sb, chain = _make_fake_supabase(insert_data=[{"id": "seq-uuid-001"}])
        session_data = _make_session_data(product_sku="fornecedores-vencedores")

        with patch("job_queue.get_arq_pool", return_value=mock_pool):
            from webhooks.handlers.checkout import handle_digital_product_checkout_completed
            await handle_digital_product_checkout_completed(sb, session_data)

        # Deve ter enfileirado 2 jobs
        assert mock_pool.enqueue_job.call_count == 2
        calls = mock_pool.enqueue_job.call_args_list

        # First call: followup
        assert calls[0][0][0] == "post_purchase_followup"
        assert calls[0][0][1] == "seq-uuid-001"

        # Second call: reengagement
        assert calls[1][0][0] == "post_purchase_reengagement"
        assert calls[1][0][1] == "seq-uuid-001"


# ─────────────────────────────────────────────────────────────────────────────
# 3. Branching em handle_checkout_session_completed
# ─────────────────────────────────────────────────────────────────────────────

class TestCheckoutHandlerDigitalProductBranching:
    """Tests for the mode=payment + product_sku branch in handle_checkout_session_completed."""

    @pytest.mark.asyncio
    async def test_payment_mode_with_product_sku_dispatches_to_digital_handler(self):
        """mode=payment + product_sku deve chamar handle_digital_product_checkout_completed."""
        sb = MagicMock()
        session_data = _make_session_data(product_sku="relatorio-oportunidade")
        event = _make_checkout_event(session_data)

        with patch(
            "webhooks.handlers.checkout.handle_digital_product_checkout_completed",
            new_callable=AsyncMock,
        ) as mock_digital:
            from webhooks.handlers.checkout import handle_checkout_session_completed
            await handle_checkout_session_completed(sb, event)
            mock_digital.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscription_mode_does_not_dispatch_to_digital_handler(self):
        """mode=subscription NAO deve chamar handle_digital_product_checkout_completed."""
        sb = MagicMock()
        # subscription: precisa de metadata com plan_id e mode=subscription
        session_data = _make_session_data(
            product_sku="relatorio-oportunidade",
            mode="subscription",
        )
        event = _make_checkout_event(session_data)

        with patch(
            "webhooks.handlers.checkout.handle_digital_product_checkout_completed",
            new_callable=AsyncMock,
        ) as mock_digital, \
            patch("webhooks.handlers.checkout.resolve_user_id", return_value=None):
            from webhooks.handlers.checkout import handle_checkout_session_completed
            await handle_checkout_session_completed(sb, event)
            mock_digital.assert_not_called()

    @pytest.mark.asyncio
    async def test_payment_mode_without_product_sku_does_not_dispatch(self):
        """mode=payment sem product_sku NAO deve chamar handler digital."""
        sb = MagicMock()
        session_data = _make_session_data(product_sku=None, mode="payment")
        event = _make_checkout_event(session_data)

        with patch(
            "webhooks.handlers.checkout.handle_digital_product_checkout_completed",
            new_callable=AsyncMock,
        ) as mock_digital, \
            patch("webhooks.handlers.checkout.resolve_user_id", return_value=None):
            from webhooks.handlers.checkout import handle_checkout_session_completed
            await handle_checkout_session_completed(sb, event)
            mock_digital.assert_not_called()

    @pytest.mark.asyncio
    async def test_intel_report_takes_precedence_over_digital_product(self):
        """product_type (Intel Report) deve ter precedencia sobre product_sku."""
        sb = MagicMock()
        session_data = _make_session_data(
            product_sku="relatorio-oportunidade",
            product_type="cnpj",
            mode="payment",
        )
        event = _make_checkout_event(session_data)

        with patch(
            "webhooks.handlers.checkout.handle_intel_report_checkout_completed",
            new_callable=AsyncMock,
        ) as mock_intel, \
            patch(
                "webhooks.handlers.checkout.handle_digital_product_checkout_completed",
                new_callable=AsyncMock,
            ) as mock_digital:
            from webhooks.handlers.checkout import handle_checkout_session_completed
            await handle_checkout_session_completed(sb, event)
            # Intel report deve ser chamado, digital product NAO
            mock_intel.assert_called_once()
            mock_digital.assert_not_called()

    @pytest.mark.asyncio
    async def test_founding_takes_precedence_over_digital_product(self):
        """source=founding (founding checkout) deve ter precedencia sobre product_sku."""
        sb = MagicMock()
        session_data = _make_session_data(
            product_sku="relatorio-oportunidade",
            source="founding",
            mode="payment",
        )
        event = _make_checkout_event(session_data)

        with patch(
            "webhooks.handlers.checkout.handle_digital_product_checkout_completed",
            new_callable=AsyncMock,
        ) as mock_digital:
            from webhooks.handlers.checkout import handle_checkout_session_completed
            await handle_checkout_session_completed(sb, event)
            # founding check primeiro — digital product NAO deve ser chamado
            mock_digital.assert_not_called()

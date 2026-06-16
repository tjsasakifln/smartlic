"""PreDunningLoop — Card expiry pre-dunning check (STORY-309)."""
import logging
from datetime import datetime, timezone, timedelta

from jobs.cron.base import BaseCronLoop

logger = logging.getLogger(__name__)

PRE_DUNNING_INTERVAL_SECONDS = 24 * 60 * 60


class PreDunningLoop(BaseCronLoop):
    """Check for cards expiring in ~7 days and send pre-dunning emails."""

    name = "pre_dunning"
    interval_seconds = PRE_DUNNING_INTERVAL_SECONDS
    initial_delay = 120.0
    error_retry_seconds = 60.0

    async def run_once(self) -> dict:
        import os
        try:
            import stripe
            stripe_key = os.getenv("STRIPE_SECRET_KEY", "")
            if not stripe_key:
                return {"sent": 0, "skipped": 0, "errors": 0, "disabled": True}

            from supabase_client import get_supabase, sb_execute
            from services.dunning import send_pre_dunning_email

            sb = get_supabase()
            now = datetime.now(timezone.utc)
            target_date = now + timedelta(days=7)
            sent = skipped = errors = 0

            subs_result = await sb_execute(
                sb.table("user_subscriptions")
                .select("user_id, stripe_customer_id")
                .eq("is_active", True).eq("subscription_status", "active")
                .not_.is_("stripe_customer_id", "null")
            )
            if not subs_result.data:
                return {"sent": 0, "skipped": 0, "errors": 0}

            for sub in subs_result.data:
                try:
                    customer_id = sub.get("stripe_customer_id")
                    user_id = sub.get("user_id")
                    if not customer_id or not user_id:
                        continue

                    customer = stripe.Customer.retrieve(
                        customer_id, api_key=stripe_key,
                        expand=["default_source", "invoice_settings.default_payment_method"],
                    )
                    pm = customer.get("invoice_settings", {}).get("default_payment_method")
                    card_info = None
                    if pm and hasattr(pm, "card"):
                        card_info = pm.card
                    elif customer.get("default_source") and hasattr(customer.default_source, "exp_month"):
                        card_info = customer.default_source

                    if not card_info:
                        skipped += 1
                        continue

                    exp_month = getattr(card_info, "exp_month", None) or card_info.get("exp_month")
                    exp_year = getattr(card_info, "exp_year", None) or card_info.get("exp_year")
                    last4 = getattr(card_info, "last4", None) or card_info.get("last4", "****")
                    if not exp_month or not exp_year:
                        skipped += 1
                        continue

                    if exp_year == target_date.year and exp_month == target_date.month:
                        await send_pre_dunning_email(user_id, last4, exp_month, exp_year)
                        sent += 1
                    else:
                        skipped += 1
                except Exception:
                    errors += 1

            logger.info("Pre-dunning: sent=%d skipped=%d errors=%d", sent, skipped, errors)
            return {"sent": sent, "skipped": skipped, "errors": errors}
        except Exception as e:
            err_name = type(e).__name__
            err_str = str(e)
            if "CircuitBreaker" in err_name or "ConnectionError" in err_name or "ConnectError" in err_str or "PGRST205" in err_str:
                logger.warning("Pre-dunning skipped (Supabase unavailable): %s", e)
            else:
                logger.error("Pre-dunning error: %s", e, exc_info=True)
            return {"sent": 0, "skipped": 0, "errors": 1, "error": str(e)}

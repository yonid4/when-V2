"""Account-level operations: deletion (and anything else that spans every
table belonging to a user). Kept separate from per-feature services so the
deletion order stays in one place."""

import logging

from app.providers.base import TokenBundle
from app.providers.registry import get_provider
from app.utils.supabase import service_client

logger = logging.getLogger(__name__)


def delete_account(user_id: str) -> None:
    """Delete a user account and all personal data they own.

    Order matters:
      1. Revoke every connected calendar's credentials via its provider. If any
         fails for an uncertain reason, abort — the provider raises
         :class:`TokenRevocationError` and the router maps it to HTTP 502.
         (Providers without a revoke endpoint, e.g. Microsoft, are no-ops.)
      2. Delete events the user is currently coordinating that are still in
         ``planning`` status. These are drafts no one's calendar depends on.
      3. Anonymize the remaining (confirmed/cancelled) events the user
         coordinated by setting ``coordinator_id = NULL`` explicitly.
      4. Purge every child row owned by the user (preferred_slots,
         event_participants, notifications, proposed_time_notes) under
         service_role. Why explicitly and not via FK cascade? The CASCADE
         triggered inside ``auth.admin.delete_user`` runs under the
         ``supabase_auth_admin`` role, and the broadcast triggers on these
         tables are not ``SECURITY DEFINER`` — they would fail to write to
         ``realtime.messages`` (whose INSERT policy is now restricted to
         ``authenticated``). Doing the deletes here under ``service_role``
         lets the broadcasts fire successfully and leaves the ``delete_user``
         cascade with nothing to do for these tables.
      5. Delete the auth user. The remaining cascade is fine because:
            - busy_slots / proposed_time_notes broadcast triggers ARE
              ``SECURITY DEFINER`` and run cleanly under any role.
            - calendar_accounts / calendar_sources have no broadcast triggers.
            - event_invitations has no broadcast triggers.
    """
    accounts = (
        service_client.table("calendar_accounts")
        .select("provider, credentials")
        .eq("user_id", user_id)
        .execute()
    )
    for acc in accounts.data or []:
        provider = get_provider(acc.get("provider") or "google")
        provider.revoke(TokenBundle(acc.get("credentials") or {}))

    service_client.table("events").delete().eq("coordinator_id", user_id).eq(
        "status", "planning"
    ).execute()

    service_client.table("events").update({"coordinator_id": None}).eq(
        "coordinator_id", user_id
    ).execute()

    # Purge user-owned rows whose broadcast triggers are NOT SECURITY DEFINER
    service_client.table("preferred_slots").delete().eq("user_id", user_id).execute()
    service_client.table("event_participants").delete().eq("user_id", user_id).execute()
    service_client.table("notifications").delete().eq("user_id", user_id).execute()

    service_client.auth.admin.delete_user(user_id)
    logger.info("Account deleted: user_id=%s", user_id)

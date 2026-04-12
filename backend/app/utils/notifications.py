from app.utils.supabase import service_client


def create_notifications(rows: list[dict]) -> None:
    """Insert one or more notification rows via the service client."""
    if rows:
        service_client.table('notifications').insert(rows).execute()

from supabase import create_client, Client
from app.config import settings

anon_client: Client = create_client(settings.supabase_url, settings.supabase_anon_key)
service_client: Client = create_client(settings.supabase_url, settings.supabase_service_role_key)


def get_authed_client(token: str) -> Client:
    """Return a Supabase client authenticated as the request user.
    This sets auth.uid() correctly so RLS policies can evaluate."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(token)
    return client

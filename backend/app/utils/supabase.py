import httpx
from supabase import create_client, Client
from app.config import settings


def _force_http1(client: Client) -> Client:
    """Replace the postgrest session's transport with an HTTP/1.1-only client.

    supabase-py 2.x uses httpx internally via postgrest-py. When the h2 package
    is installed httpx defaults to HTTP/2, which causes Supabase's PostgREST to
    drop connections mid-stream (RemoteProtocolError). Forcing HTTP/1.1 here
    prevents that without touching any router or service code.
    """
    http1_client = httpx.Client(http2=False)
    client.postgrest._session = http1_client
    return client


anon_client: Client = _force_http1(create_client(settings.supabase_url, settings.supabase_anon_key))
service_client: Client = _force_http1(create_client(settings.supabase_url, settings.supabase_service_role_key))


def get_authed_client(token: str) -> Client:
    """Return a Supabase client authenticated as the request user.
    This sets auth.uid() correctly so RLS policies can evaluate."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(token)
    return _force_http1(client)

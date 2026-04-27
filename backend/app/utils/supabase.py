import httpx
from supabase import create_client, Client
from app.config import settings


def _force_http1(client: Client) -> Client:
    """Replace the postgrest session transport with HTTP/1.1.

    postgrest-py hardcodes http2=True in create_session. When h2 is installed
    Supabase's PostgREST drops connections mid-stream (RemoteProtocolError).
    We rebuild the session with http2=False, preserving base_url and headers.
    """
    old = client.postgrest.session
    client.postgrest.session = httpx.Client(
        base_url=old.base_url,
        headers=dict(old.headers),
        timeout=old.timeout,
        follow_redirects=True,
        http2=False,
    )
    return client


anon_client: Client = _force_http1(create_client(settings.supabase_url, settings.supabase_anon_key))
service_client: Client = _force_http1(create_client(settings.supabase_url, settings.supabase_service_role_key))


def get_authed_client(token: str) -> Client:
    """Return a Supabase client authenticated as the request user.
    This sets auth.uid() correctly so RLS policies can evaluate."""
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(token)
    return _force_http1(client)

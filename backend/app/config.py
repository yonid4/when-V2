from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    google_calendar_redirect_uri: str = "http://localhost:8000/api/calendar-accounts/callback"
    # Microsoft (Outlook / Graph) calendar. Left blank disables the provider;
    # google-only deployments don't need these set.
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_calendar_redirect_uri: str = (
        "http://localhost:8000/api/calendar-accounts/callback/microsoft"
    )
    # Gemini (agentic chat). Left blank disables chat; deployments without an
    # API key run normally with the chat feature turned off.
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 10080  # 7 days
    frontend_url: str = "http://localhost:3000"
    # Root log level. INFO surfaces the per-turn chat latency traces
    # (agent_service/tracing.py); set to WARNING to see only slow turns.
    log_level: str = "INFO"
    # Allow OAuth over plain HTTP. Local development only — never enable in a
    # deployed environment.
    oauth_insecure_transport: bool = False


settings = Settings()  # type: ignore[call-arg]

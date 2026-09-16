"""
Configuration centralisée de l'application.

Toutes les variables d'environnement transitent par cette classe unique
(Settings) afin d'avoir une seule source de vérité, typée et validée
au démarrage de l'application (fail-fast si une valeur est invalide).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application ---
    app_name: str = "JARVIS AI"
    app_env: str = "development"
    debug: bool = True

    # --- Sécurité ---
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 30
    encryption_key: str | None = None  # AES-256 (64 car. hex) — chiffrement des tokens d'intégration au repos

    # --- Base de données ---
    database_url: str
    postgres_user: str = "jarvis"
    postgres_password: str = "jarvis"
    postgres_db: str = "jarvis_db"

    # --- Redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Fournisseurs IA ---
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    elevenlabs_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434"

    # --- Intégrations externes (étape 7) ---
    google_oauth_client_id: str | None = None
    google_oauth_client_secret: str | None = None
    google_oauth_redirect_uri: str = "http://localhost:8000/api/v1/integrations/google/callback"
    whatsapp_access_token: str | None = None
    whatsapp_phone_number_id: str | None = None

    # --- CORS ---
    allowed_origins: str = "*"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def cors_origins(self) -> list[str]:
        if self.allowed_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.allowed_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    """Renvoie une instance mise en cache des réglages (évite de re-parser l'env)."""
    return Settings()


settings = get_settings()

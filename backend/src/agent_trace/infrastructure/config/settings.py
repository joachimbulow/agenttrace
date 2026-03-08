from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    Configuration is loaded from:
    1. Environment variables (highest priority)
    2. .env file
    
    Example .env file:
        DATABASE_URL=sqlite+aiosqlite:///./data/agent_trace.db
        API_HOST=0.0.0.0
        API_PORT=8000
        LOG_LEVEL=INFO
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )
    
    # Database
    database_url: str = "sqlite+aiosqlite:///./data/agent_trace.db"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_title: str = "Agent Trace"
    api_version: str = "0.1.0"
    api_description: str = "Local visual debugger for AI agents"
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # SDK
    sdk_batch_size: int = 100
    sdk_export_timeout_ms: int = 5000
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.log_level.upper() == "DEBUG"
    
    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return "sqlite" in self.database_url.lower()


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance.
    
    Uses lru_cache to ensure settings are only loaded once.
    
    Returns:
        Settings instance.
    """
    return Settings()
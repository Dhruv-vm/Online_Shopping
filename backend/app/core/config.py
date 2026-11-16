from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", "backend/.env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    PROJECT_NAME: str = "BASKET Backend"
    API_V1_STR: str = "/api/v1"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"

    # Security & Auth
    SECRET_KEY: SecretStr = SecretStr(
        "insecure-default-development-key-change-in-production"
    )
    JWT_SECRET_KEY: SecretStr = SecretStr(
        "insecure-jwt-secret-key-change-in-production-min-256-bit"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    CSRF_SECRET_KEY: SecretStr = SecretStr(
        "insecure-csrf-secret-key-change-in-production"
    )
    ALLOWED_HOSTS: list[str] = ["*"]
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Database (Aiven PostgreSQL)
    DATABASE_URL: str | None = None
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 5
    DATABASE_SSL_MODE: str = "require"

    # Kafka (Aiven Kafka)
    KAFKA_BOOTSTRAP_SERVERS: str | None = None
    KAFKA_SECURITY_PROTOCOL: str = "SSL"
    KAFKA_SSL_CA_LOCATION: str | None = None
    KAFKA_SSL_CERTIFICATE_LOCATION: str | None = None
    KAFKA_SSL_KEY_LOCATION: str | None = None

    # OpenSearch (Aiven OpenSearch)
    OPENSEARCH_URL: str | None = None
    OPENSEARCH_USERNAME: str | None = None
    OPENSEARCH_PASSWORD: SecretStr | None = None
    OPENSEARCH_INDEX_PREFIX: str = "basket"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json

                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, list):
            return [str(item) for item in v]
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def has_database(self) -> bool:
        return bool(self.DATABASE_URL and self.DATABASE_URL.strip())


settings = Settings()

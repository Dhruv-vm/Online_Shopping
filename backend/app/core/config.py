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

    # Commerce Delivery Policy (Configurable in Phase 2C)
    # NOTE: ₹49.00 standard fee and ₹499.00 free delivery threshold are provisional baseline
    # defaults for development and demonstration, NOT approved universal platform business policies.
    # Production systems should configure these via environment variables or per-retailer contracts.
    DEFAULT_DELIVERY_FEE_PAISE: int = 4900  # ₹49.00 (Provisional baseline)
    DEFAULT_FREE_DELIVERY_THRESHOLD_PAISE: int = 49900  # ₹499.00 (Provisional baseline)

    # Inventory Reservation Policy (Phase 2D)
    RESERVATION_TTL_MINUTES: int = 10  # 10-minute hold for active stock reservation

    # Internal Service Security (Phase 2D - background worker crons, internal tasks)
    # Must be set via environment variable. No hardcoded default is permitted in production.
    INTERNAL_SERVICE_KEY: SecretStr | None = None

    # Razorpay Payment Gateway (Phase 2F Sandbox)
    RAZORPAY_KEY_ID: SecretStr | None = SecretStr("rzp_test_basket_mock_key_id")
    RAZORPAY_KEY_SECRET: SecretStr | None = SecretStr(
        "mock_secret_key_at_least_16_chars"
    )
    RAZORPAY_WEBHOOK_SECRET: SecretStr | None = SecretStr(
        "mock_webhook_secret_at_least_16_chars"
    )
    RAZORPAY_BASE_URL: str = "https://api.razorpay.com/v1"
    RAZORPAY_CONNECT_TIMEOUT_SECONDS: float = 5.0
    RAZORPAY_READ_TIMEOUT_SECONDS: float = 10.0

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

    @field_validator("INTERNAL_SERVICE_KEY", mode="after")
    @classmethod
    def validate_internal_service_key(
        cls, v: SecretStr | None, info
    ) -> SecretStr | None:
        env = info.data.get("ENVIRONMENT", "development")
        if env == "production":
            if not v or not v.get_secret_value():
                raise ValueError(
                    "INTERNAL_SERVICE_KEY must be configured in production."
                )
            secret = v.get_secret_value()
            weak_keys = {
                "insecure-internal-service-key-change-in-production",
                "internal-key",
                "secret",
                "admin",
                "password",
                "changeme",
                "dev-internal-service-key-min-32-chars-long-secret",
            }
            if secret in weak_keys or len(secret) < 32:
                raise ValueError(
                    "INTERNAL_SERVICE_KEY in production must be a secure, unpredictable key with at least 32 characters."
                )
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def has_database(self) -> bool:
        return bool(self.DATABASE_URL and self.DATABASE_URL.strip())


settings = Settings()

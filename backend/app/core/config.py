from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[".env", "backend/.env"],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        hide_input_in_errors=True,
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
    KAFKA_SASL_MECHANISM: str = "SCRAM-SHA-256"
    KAFKA_SASL_USERNAME: str | None = None
    KAFKA_SASL_PASSWORD: SecretStr | None = None
    KAFKA_CLIENT_ID: str = "basket-backend"
    KAFKA_PRODUCER_ACKS: str = "all"
    KAFKA_PRODUCER_RETRIES: int = 5
    KAFKA_PRODUCER_TIMEOUT_SECONDS: float = 2.0

    # Outbox Publisher (Phase 3B)
    OUTBOX_POLL_INTERVAL_SECONDS: float = 1.0
    OUTBOX_BATCH_SIZE: int = 20
    OUTBOX_LEASE_SECONDS: float = 30.0
    OUTBOX_BATCH_WINDOW_SECONDS: float = 15.0
    OUTBOX_PER_EVENT_TIMEOUT_SECONDS: float = 2.0
    OUTBOX_MAX_RETRIES: int = 5

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

    @field_validator(
        "RAZORPAY_KEY_ID",
        "RAZORPAY_KEY_SECRET",
        "RAZORPAY_WEBHOOK_SECRET",
        mode="after",
    )
    @classmethod
    def validate_razorpay_credentials(
        cls, v: SecretStr | None, info
    ) -> SecretStr | None:
        env = str(info.data.get("ENVIRONMENT", "development")).lower()
        if env == "production":
            field_name = info.field_name
            if not v or not v.get_secret_value() or not v.get_secret_value().strip():
                raise ValueError(f"{field_name} must be configured in production.")
            secret = v.get_secret_value().strip()

            if field_name == "RAZORPAY_KEY_ID":
                if secret.startswith("rzp_test_"):
                    raise ValueError(
                        "RAZORPAY_KEY_ID cannot use test credentials (rzp_test_) in production; live key (rzp_live_) is required."
                    )
                if not secret.startswith("rzp_live_"):
                    raise ValueError(
                        "RAZORPAY_KEY_ID must begin with 'rzp_live_' in production."
                    )

            secret_lower = secret.lower()
            known_mock_values = {
                "mock_secret_key_at_least_16_chars",
                "mock_webhook_secret_at_least_16_chars",
                "replace_with_your_key_secret_at_least_16_chars",
                "replace_with_your_webhook_secret_at_least_16_chars",
                "secret",
                "mock",
                "example",
                "placeholder",
                "changeme",
                "change-me",
            }
            if (
                secret in known_mock_values
                or "mock" in secret_lower
                or "replace" in secret_lower
                or "placeholder" in secret_lower
                or "example" in secret_lower
            ):
                raise ValueError(
                    f"{field_name} must be configured with genuine production credentials; mock or placeholder values are not permitted in production."
                )
            if (
                field_name in ("RAZORPAY_KEY_SECRET", "RAZORPAY_WEBHOOK_SECRET")
                and len(secret) < 16
            ):
                raise ValueError(
                    f"{field_name} in production must have at least 16 characters."
                )
        return v

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

    @field_validator("KAFKA_SECURITY_PROTOCOL", mode="after")
    @classmethod
    def validate_kafka_security_protocol(cls, v: str, info) -> str:
        protocol = v.upper().strip()
        valid_protocols = {"SSL", "SASL_SSL", "PLAINTEXT", "SASL_PLAINTEXT"}
        if protocol not in valid_protocols:
            raise ValueError(
                f"KAFKA_SECURITY_PROTOCOL must be one of {sorted(valid_protocols)}"
            )
        env = str(info.data.get("ENVIRONMENT", "development")).lower()
        if env == "production" and protocol in ("PLAINTEXT", "SASL_PLAINTEXT"):
            raise ValueError(
                f"KAFKA_SECURITY_PROTOCOL cannot be '{protocol}' in production; SSL or SASL_SSL is required."
            )
        return protocol

    @field_validator("KAFKA_PRODUCER_ACKS", mode="after")
    @classmethod
    def validate_kafka_producer_acks(cls, v: str, info) -> str:
        valid_acks = {"all", "-1", "0", "1"}
        v_str = str(v).lower().strip()
        if v_str not in valid_acks:
            raise ValueError(f"KAFKA_PRODUCER_ACKS must be one of {sorted(valid_acks)}")
        env = str(info.data.get("ENVIRONMENT", "development")).lower()
        if env == "production" and v_str not in ("all", "-1"):
            raise ValueError(
                "KAFKA_PRODUCER_ACKS must be 'all' (or '-1') in production; acks=0 and acks=1 are prohibited."
            )
        return v_str

    @field_validator("KAFKA_SASL_PASSWORD", mode="after")
    @classmethod
    def validate_kafka_sasl_credentials(
        cls, v: SecretStr | None, info
    ) -> SecretStr | None:
        env = str(info.data.get("ENVIRONMENT", "development")).lower()
        protocol = str(info.data.get("KAFKA_SECURITY_PROTOCOL", "SSL")).upper()
        servers = info.data.get("KAFKA_BOOTSTRAP_SERVERS")
        if (
            env == "production"
            and servers
            and protocol in ("SASL_SSL", "SASL_PLAINTEXT")
        ):
            if not v or not v.get_secret_value() or not v.get_secret_value().strip():
                raise ValueError(
                    "KAFKA_SASL_PASSWORD must be configured in production when using SASL."
                )
            secret = v.get_secret_value().strip().lower()
            if "mock" in secret or "example" in secret or "placeholder" in secret:
                raise ValueError(
                    "KAFKA_SASL_PASSWORD cannot be a placeholder or mock value in production."
                )
        return v

    @field_validator("KAFKA_BOOTSTRAP_SERVERS", mode="before")
    @classmethod
    def clean_kafka_bootstrap_servers(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return str(v)

    @field_validator("KAFKA_BOOTSTRAP_SERVERS", mode="after")
    @classmethod
    def validate_kafka_bootstrap_servers(cls, v: str | None, info) -> str | None:
        if v is None:
            return None
        env = str(info.data.get("ENVIRONMENT", "development")).lower()
        if env == "production":
            cleaned_lower = v.lower()
            if (
                "mock" in cleaned_lower
                or "example" in cleaned_lower
                or "localhost" in cleaned_lower
                or "127.0.0.1" in cleaned_lower
            ):
                raise ValueError(
                    "KAFKA_BOOTSTRAP_SERVERS in production cannot use mock or localhost addresses."
                )
        return v

    @field_validator("OUTBOX_BATCH_SIZE", mode="after")
    @classmethod
    def validate_outbox_batch_size(cls, v: int) -> int:
        if v < 1 or v > 20:
            raise ValueError("OUTBOX_BATCH_SIZE must be between 1 and 20.")
        return v

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT.lower() == "production"

    @property
    def has_database(self) -> bool:
        return bool(self.DATABASE_URL and self.DATABASE_URL.strip())

    @property
    def has_kafka(self) -> bool:
        return bool(
            self.KAFKA_BOOTSTRAP_SERVERS and self.KAFKA_BOOTSTRAP_SERVERS.strip()
        )


settings = Settings()

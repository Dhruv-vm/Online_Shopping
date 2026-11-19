import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_defaults():
    s = Settings(ENVIRONMENT="development")
    assert s.ENVIRONMENT == "development"
    assert s.is_production is False
    assert s.PROJECT_NAME == "BASKET Backend"
    # SecretStr should not reveal plain text on str()
    assert "insecure" not in str(s.SECRET_KEY)
    assert s.SECRET_KEY.get_secret_value() != ""


def test_cors_origins_parsing():
    s = Settings(CORS_ORIGINS=["http://localhost:3000"])
    assert "http://localhost:3000" in s.CORS_ORIGINS


def test_production_rejects_test_key_ids_with_any_suffix():
    test_key_variants = [
        "rzp_test_any_suffix",
        "rzp_test_1234567890abcdef",
        "rzp_test_live_lookalike",
        "rzp_test_something_else",
    ]
    for key_id in test_key_variants:
        with pytest.raises(
            ValidationError,
            match="cannot use test credentials \\(rzp_test_\\) in production",
        ) as exc_info:
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="a" * 32,
                JWT_SECRET_KEY="b" * 32,
                INTERNAL_SERVICE_KEY="c" * 32,
                RAZORPAY_KEY_ID=key_id,
                RAZORPAY_KEY_SECRET="productionsecret16chars",
                RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
            )
        # Error must never expose secret values
        assert key_id not in str(exc_info.value)

    # Also reject keys not starting with rzp_live_
    non_live_keys = ["custom_key_id_12345", "rzp_prod_12345", "live_key_without_rzp"]
    for key_id in non_live_keys:
        with pytest.raises(
            ValidationError, match="must begin with 'rzp_live_' in production"
        ):
            Settings(
                ENVIRONMENT="production",
                SECRET_KEY="a" * 32,
                JWT_SECRET_KEY="b" * 32,
                INTERNAL_SERVICE_KEY="c" * 32,
                RAZORPAY_KEY_ID=key_id,
                RAZORPAY_KEY_SECRET="productionsecret16chars",
                RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
            )


def test_production_rejects_missing_or_mock_razorpay_credentials():
    # Production with placeholder secret must fail
    with pytest.raises(ValidationError, match="genuine production credentials"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
            INTERNAL_SERVICE_KEY="c" * 32,
            RAZORPAY_KEY_ID="rzp_live_realproductionkey123",
            RAZORPAY_KEY_SECRET="mock_secret_key_at_least_16_chars",
            RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
        )

    # Production with example secret must fail
    with pytest.raises(ValidationError, match="genuine production credentials"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
            INTERNAL_SERVICE_KEY="c" * 32,
            RAZORPAY_KEY_ID="rzp_live_realproductionkey123",
            RAZORPAY_KEY_SECRET="example_secret_16_chars",
            RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
        )

    # Production with placeholder webhook secret must fail
    with pytest.raises(ValidationError, match="genuine production credentials"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
            INTERNAL_SERVICE_KEY="c" * 32,
            RAZORPAY_KEY_ID="rzp_live_realproductionkey123",
            RAZORPAY_KEY_SECRET="productionsecret16chars",
            RAZORPAY_WEBHOOK_SECRET="placeholder_secret_16",
        )

    # Production with short secret (<16 chars) must fail
    with pytest.raises(ValidationError, match="at least 16 characters"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
            INTERNAL_SERVICE_KEY="c" * 32,
            RAZORPAY_KEY_ID="rzp_live_realproductionkey123",
            RAZORPAY_KEY_SECRET="shortsecret",
            RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
        )

    # Production with None key id must fail
    with pytest.raises(ValidationError, match="must be configured in production"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
            INTERNAL_SERVICE_KEY="c" * 32,
            RAZORPAY_KEY_ID=None,
            RAZORPAY_KEY_SECRET="productionsecret16chars",
            RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
        )

    # Production with missing key id must fail
    with pytest.raises(ValidationError, match="must be configured in production"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
            INTERNAL_SERVICE_KEY="c" * 32,
            RAZORPAY_KEY_ID="",
            RAZORPAY_KEY_SECRET="productionsecret16chars",
            RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
        )

    # Production with whitespace key id must fail
    with pytest.raises(ValidationError, match="must be configured in production"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
            INTERNAL_SERVICE_KEY="c" * 32,
            RAZORPAY_KEY_ID="   ",
            RAZORPAY_KEY_SECRET="productionsecret16chars",
            RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
        )


def test_production_accepts_valid_credentials():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 32,
        JWT_SECRET_KEY="b" * 32,
        INTERNAL_SERVICE_KEY="c" * 32,
        RAZORPAY_KEY_ID="rzp_live_realproductionkey123",
        RAZORPAY_KEY_SECRET="productionsecret16chars",
        RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
        KAFKA_BOOTSTRAP_SERVERS="",
    )
    assert s.is_production is True
    assert s.RAZORPAY_KEY_ID.get_secret_value() == "rzp_live_realproductionkey123"
    assert "rzp_live_realproductionkey123" not in str(s.RAZORPAY_KEY_ID)
    assert "productionsecret16chars" not in str(s.RAZORPAY_KEY_SECRET)
    assert "productionwebhooksecret16chars" not in str(s.RAZORPAY_WEBHOOK_SECRET)


def test_development_allows_mock_credentials():
    s = Settings(
        ENVIRONMENT="development",
        RAZORPAY_KEY_ID="rzp_test_basket_mock_key_id",
        RAZORPAY_KEY_SECRET="mock_secret_key_at_least_16_chars",
        RAZORPAY_WEBHOOK_SECRET="mock_webhook_secret_at_least_16_chars",
    )
    assert s.is_production is False
    assert s.RAZORPAY_KEY_ID.get_secret_value() == "rzp_test_basket_mock_key_id"


def test_clean_opensearch_url_strips_credentials():
    # Embedded credentials should be stripped without leaking
    s = Settings(
        ENVIRONMENT="development",
        OPENSEARCH_URL="https://avnadmin:secretpassword123@basket-opensearch.aivencloud.com:10494",
    )
    assert s.OPENSEARCH_URL == "https://basket-opensearch.aivencloud.com:10494"
    assert "avnadmin" not in s.OPENSEARCH_URL
    assert "secretpassword123" not in s.OPENSEARCH_URL

    # Clean URL should be preserved intact
    s2 = Settings(
        ENVIRONMENT="development",
        OPENSEARCH_URL="https://basket-opensearch.aivencloud.com:10494/",
    )
    assert s2.OPENSEARCH_URL == "https://basket-opensearch.aivencloud.com:10494"


def test_resolve_kafka_ssl_ca_location():
    # Resolves relative path to ca.pem if it exists in infra/aiven/certs/ca.pem
    s = Settings(
        ENVIRONMENT="development",
        KAFKA_SSL_CA_LOCATION="infra/aiven/certs/ca.pem",
    )
    assert s.KAFKA_SSL_CA_LOCATION is not None
    assert s.KAFKA_SSL_CA_LOCATION.endswith("infra/aiven/certs/ca.pem")
    assert s.KAFKA_SSL_CA_LOCATION.startswith("/")

    # None or empty string returns None
    s_none = Settings(ENVIRONMENT="development", KAFKA_SSL_CA_LOCATION=None)
    assert s_none.KAFKA_SSL_CA_LOCATION is None
    s_empty = Settings(ENVIRONMENT="development", KAFKA_SSL_CA_LOCATION="")
    assert s_empty.KAFKA_SSL_CA_LOCATION is None


def test_kafka_auth_kwargs_sasl_ssl():
    from app.core.events.kafka import build_kafka_auth_kwargs, build_kafka_ssl_context

    s = Settings(
        ENVIRONMENT="development",
        KAFKA_BOOTSTRAP_SERVERS="kafka.example.com:9092",
        KAFKA_SECURITY_PROTOCOL="SASL_SSL",
        KAFKA_SASL_MECHANISM="SCRAM-SHA-256",
        KAFKA_SASL_USERNAME="avnadmin",
        KAFKA_SASL_PASSWORD="test_password_123",
        KAFKA_SSL_CA_LOCATION="infra/aiven/certs/ca.pem",
    )

    kwargs = build_kafka_auth_kwargs(s)
    assert kwargs["security_protocol"] == "SASL_SSL"
    assert kwargs["sasl_mechanism"] == "SCRAM-SHA-256"
    assert kwargs["sasl_plain_username"] == "avnadmin"
    assert kwargs["sasl_plain_password"] == "test_password_123"
    assert kwargs["ssl_context"] is not None

    ssl_ctx = build_kafka_ssl_context(s)
    assert ssl_ctx is not None


def test_kafka_auth_kwargs_plaintext():
    from app.core.events.kafka import build_kafka_auth_kwargs

    s = Settings(
        ENVIRONMENT="development",
        KAFKA_BOOTSTRAP_SERVERS="localhost:9092",
        KAFKA_SECURITY_PROTOCOL="PLAINTEXT",
    )
    kwargs = build_kafka_auth_kwargs(s)
    assert kwargs == {"security_protocol": "PLAINTEXT"}

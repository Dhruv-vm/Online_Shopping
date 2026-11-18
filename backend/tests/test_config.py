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


def test_production_rejects_missing_or_mock_razorpay_credentials():
    # Production with mock key id must fail
    with pytest.raises(ValidationError, match="genuine production credentials"):
        Settings(
            ENVIRONMENT="production",
            SECRET_KEY="a" * 32,
            JWT_SECRET_KEY="b" * 32,
            INTERNAL_SERVICE_KEY="c" * 32,
            RAZORPAY_KEY_ID="rzp_test_basket_mock_key_id",
            RAZORPAY_KEY_SECRET="productionsecret16chars",
            RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
        )

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


def test_production_accepts_valid_credentials():
    s = Settings(
        ENVIRONMENT="production",
        SECRET_KEY="a" * 32,
        JWT_SECRET_KEY="b" * 32,
        INTERNAL_SERVICE_KEY="c" * 32,
        RAZORPAY_KEY_ID="rzp_live_realproductionkey123",
        RAZORPAY_KEY_SECRET="productionsecret16chars",
        RAZORPAY_WEBHOOK_SECRET="productionwebhooksecret16chars",
    )
    assert s.is_production is True
    assert s.RAZORPAY_KEY_ID.get_secret_value() == "rzp_live_realproductionkey123"
    assert "rzp_live_realproductionkey123" not in str(s.RAZORPAY_KEY_ID)


def test_development_allows_mock_credentials():
    s = Settings(
        ENVIRONMENT="development",
        RAZORPAY_KEY_ID="rzp_test_basket_mock_key_id",
        RAZORPAY_KEY_SECRET="mock_secret_key_at_least_16_chars",
        RAZORPAY_WEBHOOK_SECRET="mock_webhook_secret_at_least_16_chars",
    )
    assert s.is_production is False

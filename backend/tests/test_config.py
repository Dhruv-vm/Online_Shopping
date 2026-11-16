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

import pytest

from portwatch_backend.core.config import Settings, validate_bind_security


def test_loopback_bind_never_requires_a_token() -> None:
    validate_bind_security(Settings(bind_host="127.0.0.1", api_token=""))
    validate_bind_security(Settings(bind_host="localhost", api_token=""))
    validate_bind_security(Settings(bind_host="::1", api_token=""))


def test_non_loopback_bind_without_a_token_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="not loopback"):
        validate_bind_security(Settings(bind_host="0.0.0.0", api_token=""))


def test_non_loopback_bind_with_a_token_is_accepted() -> None:
    validate_bind_security(Settings(bind_host="0.0.0.0", api_token="secret"))


def test_cors_wildcard_is_rejected() -> None:
    with pytest.raises(ValueError, match="wildcard"):
        Settings(cors_allow_origins=["*"])


def test_cors_wildcard_mixed_with_real_origins_is_still_rejected() -> None:
    with pytest.raises(ValueError, match="wildcard"):
        Settings(cors_allow_origins=["http://localhost:5173", "*"])

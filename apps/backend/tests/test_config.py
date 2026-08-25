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


# --- collector_poll_interval_seconds -------------------------------------


def test_poll_interval_accepts_a_normal_positive_value() -> None:
    assert Settings(collector_poll_interval_seconds=5.0).collector_poll_interval_seconds == 5.0


@pytest.mark.parametrize("interval", [0, -1.0, float("inf"), float("nan")])
def test_poll_interval_rejects_non_finite_or_non_positive_values(interval: float) -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        Settings(collector_poll_interval_seconds=interval)


# --- port_range_start / port_range_end -----------------------------------


@pytest.mark.parametrize("port", [-1, 65536, 100_000])
def test_port_range_bounds_reject_values_outside_0_65535(port: int) -> None:
    with pytest.raises(ValueError, match="between 0 and 65535"):
        Settings(port_range_start=port)
    with pytest.raises(ValueError, match="between 0 and 65535"):
        Settings(port_range_end=port)


def test_port_range_accepts_the_full_valid_boundary() -> None:
    settings = Settings(port_range_start=0, port_range_end=65535)
    assert settings.port_range_start == 0
    assert settings.port_range_end == 65535


def test_port_range_start_after_end_is_rejected() -> None:
    with pytest.raises(ValueError, match="port_range_start must be less than or equal"):
        Settings(port_range_start=2000, port_range_end=1000)


def test_port_range_start_equal_to_end_is_accepted() -> None:
    settings = Settings(port_range_start=8080, port_range_end=8080)
    assert settings.port_range_start == settings.port_range_end == 8080


# --- log_level -------------------------------------------------------------


def test_log_level_is_normalized_to_uppercase() -> None:
    assert Settings(log_level="debug").log_level == "DEBUG"


def test_log_level_rejects_an_unknown_value() -> None:
    with pytest.raises(ValueError, match="log_level must be one of"):
        Settings(log_level="TRACE")


# --- docker_proxy_url / netprobe_url ---------------------------------------


def test_netprobe_url_none_is_accepted_and_disables_host_port_scanning() -> None:
    assert Settings(netprobe_url=None).netprobe_url is None


@pytest.mark.parametrize(
    "url",
    [
        "http://docker-socket-proxy:2375",
        "https://127.0.0.1:2375",
        "http://[::1]:2375",
    ],
)
def test_service_urls_accept_absolute_http_and_https_urls(url: str) -> None:
    assert Settings(docker_proxy_url=url).docker_proxy_url == url
    assert Settings(netprobe_url=url).netprobe_url == url


def test_service_url_rejects_a_url_with_internal_whitespace() -> None:
    with pytest.raises(ValueError, match="whitespace"):
        Settings(docker_proxy_url="http://docker socket-proxy:2375")


def test_service_url_rejects_leading_or_trailing_whitespace() -> None:
    with pytest.raises(ValueError, match="whitespace"):
        Settings(docker_proxy_url=" http://docker-socket-proxy:2375")


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "docker-socket-proxy:2375",  # no scheme
        "ftp://docker-socket-proxy:2375",  # wrong scheme
        "http://",  # no hostname
    ],
)
def test_service_url_rejects_non_http_or_hostless_values(url: str) -> None:
    with pytest.raises(ValueError, match="absolute HTTP or HTTPS URL"):
        Settings(docker_proxy_url=url)


def test_service_url_rejects_an_invalid_port() -> None:
    with pytest.raises(ValueError, match="invalid port"):
        Settings(docker_proxy_url="http://docker-socket-proxy:not-a-port")


def test_service_url_rejects_embedded_credentials() -> None:
    with pytest.raises(ValueError, match="must not contain credentials"):
        Settings(docker_proxy_url="http://user:pass@docker-socket-proxy:2375")


# --- api_token ---------------------------------------------------------------


def test_api_token_empty_string_is_accepted_as_auth_disabled() -> None:
    assert Settings(api_token="").api_token == ""


def test_api_token_whitespace_only_is_rejected() -> None:
    with pytest.raises(ValueError, match="only whitespace"):
        Settings(api_token="   ")

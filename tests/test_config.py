import pytest

from ohe.config import derive_runtime_api_url, resolve_base_url, resolve_settings


def test_derive_standard_layout():
    assert (
        derive_runtime_api_url("https://app.example.com")
        == "https://runtime-api.example.com"
    )


def test_derive_multi_label_base_domain():
    assert (
        derive_runtime_api_url("https://app.ohe.customer.co.uk")
        == "https://runtime-api.ohe.customer.co.uk"
    )


def test_derive_adds_scheme_and_drops_path():
    assert (
        derive_runtime_api_url("app.example.com/some/path")
        == "https://runtime-api.example.com"
    )


def test_derive_preserves_port():
    assert (
        derive_runtime_api_url("https://app.example.com:8443")
        == "https://runtime-api.example.com:8443"
    )


def test_derive_rejects_non_app_host():
    with pytest.raises(ValueError, match="standard 'app.<base-domain>' layout"):
        derive_runtime_api_url("https://openhands.example.com")


def test_derive_rejects_bare_host_without_base_domain():
    with pytest.raises(ValueError):
        derive_runtime_api_url("https://app")


def test_resolve_base_url_prefers_explicit_override():
    settings = resolve_settings(
        app_url="https://app.example.com",
        runtime_api_url="https://rt.internal.example.com",
    )
    assert resolve_base_url(settings) == "https://rt.internal.example.com"


def test_resolve_base_url_derives_from_app_url():
    settings = resolve_settings(app_url="https://app.example.com")
    assert resolve_base_url(settings) == "https://runtime-api.example.com"


def test_resolve_base_url_requires_something():
    settings = resolve_settings()
    with pytest.raises(ValueError, match="No app or Runtime API URL"):
        resolve_base_url(settings)


def test_env_precedence_option_over_env():
    settings = resolve_settings(
        app_url="https://app.opt.example.com",
        environ={"OHE_APP_URL": "https://app.env.example.com"},
    )
    assert settings.app_url == "https://app.opt.example.com"


def test_env_ohe_prefix_wins_over_bare_name():
    settings = resolve_settings(
        environ={
            "OHE_APP_URL": "https://app.preferred.example.com",
            "APP_URL": "https://app.compat.example.com",
        }
    )
    assert settings.app_url == "https://app.preferred.example.com"

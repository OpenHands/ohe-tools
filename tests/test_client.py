import pytest

from ohe.runtime_api import (
    AdminDisabledError,
    AuthError,
    NotFoundError,
    RuntimeApiClient,
    RuntimeApiError,
)

CONFIG_BODY = {
    "image": "ghcr.io/your-org/openhands-php:8.4-v1",
    "working_dir": "/workspace",
    "command": ["/agent-server"],
    "environment": {"FOO": "bar"},
    "count": 1,
}


def _client(base_url, **kw):
    return RuntimeApiClient(
        base_url,
        api_key="test-api-key",
        admin_password="s3cret",
        base_backoff=0.0,
        sleep=lambda _s: None,
        **kw,
    )


def test_list_empty(fake_api):
    base_url, _ = fake_api
    assert _client(base_url).list_configs() == []


def test_save_then_list_and_get(fake_api):
    base_url, _ = fake_api
    client = _client(base_url)
    saved = client.save_config("php-web", dict(CONFIG_BODY))
    assert saved["name"] == "php-web"
    assert saved["source"] == "db"
    assert saved["image"] == CONFIG_BODY["image"]

    listed = client.list_configs()
    assert [c["name"] for c in listed] == ["php-web"]
    assert client.get_config("php-web")["count"] == 1
    assert client.get_config("missing") is None


def test_save_authenticates_via_challenge_response(fake_api):
    base_url, state = fake_api
    client = _client(base_url)
    client.save_config("a", dict(CONFIG_BODY))
    # A real JWT-style token was issued and cached by the client.
    assert client._admin_token is not None
    assert state.token_valid(client._admin_token)


def test_delete_returns_message(fake_api):
    base_url, _ = fake_api
    client = _client(base_url)
    client.save_config("php-web", dict(CONFIG_BODY))
    resp = client.delete_config("php-web")
    assert "deleted successfully" in resp["message"]
    assert client.list_configs() == []


def test_delete_missing_raises_not_found(fake_api):
    base_url, _ = fake_api
    with pytest.raises(NotFoundError):
        _client(base_url).delete_config("nope")


def test_list_requires_some_credential(fake_api):
    base_url, _ = fake_api
    client = RuntimeApiClient(base_url)  # no api key, no admin password
    with pytest.raises(AuthError):
        client.list_configs()


def test_list_derives_api_key_from_admin_password(fake_api):
    # No explicit API key: the client logs in as admin and pulls a key value
    # from /api/admin/api-keys, then uses it for the read call.
    base_url, _ = fake_api
    client = RuntimeApiClient(
        base_url, admin_password="s3cret", base_backoff=0.0, sleep=lambda _s: None
    )
    client.save_config("php-web", dict(CONFIG_BODY))
    assert [c["name"] for c in client.list_configs()] == ["php-web"]
    assert client._resolved_api_key == "test-api-key"


def test_wrong_api_key_is_auth_error(fake_api):
    base_url, _ = fake_api
    client = RuntimeApiClient(base_url, api_key="wrong")
    with pytest.raises(AuthError):
        client.list_configs()


def test_admin_disabled_raises(fake_api):
    base_url, state = fake_api
    state.admin_password = None  # server has no admin password configured
    client = _client(base_url)
    with pytest.raises(AdminDisabledError):
        client.save_config("x", dict(CONFIG_BODY))


def test_wrong_admin_password_is_auth_error(fake_api):
    base_url, _ = fake_api
    client = RuntimeApiClient(
        base_url, api_key="test-api-key", admin_password="wrong"
    )
    with pytest.raises(AuthError):
        client.save_config("x", dict(CONFIG_BODY))


def test_retries_transient_503_then_succeeds(fake_api):
    base_url, state = fake_api
    state.flaky["/api/warm-runtime-configs"] = 2  # fail twice, then succeed
    client = _client(base_url, max_retries=3)
    assert client.list_configs() == []
    assert state.flaky["/api/warm-runtime-configs"] == 0


def test_retries_exhausted_raises(fake_api):
    base_url, state = fake_api
    state.flaky["/api/warm-runtime-configs"] = 5
    client = _client(base_url, max_retries=2)
    with pytest.raises(RuntimeApiError):
        client.list_configs()

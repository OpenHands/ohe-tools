import json

from click.testing import CliRunner

from ohe.cli import main

CONFIG_BODY = {
    "image": "ghcr.io/your-org/openhands-php:8.4-v1",
    "working_dir": "/workspace",
    "command": ["/agent-server"],
    "environment": {"FOO": "bar"},
    "count": 1,
}


def _env(base_url):
    return {
        "OHE_RUNTIME_API_URL": base_url,
        "OHE_API_KEY": "test-api-key",
        "OHE_ADMIN_PASSWORD": "s3cret",
    }


def test_list_empty_table(fake_api):
    base_url, _ = fake_api
    result = CliRunner().invoke(main, ["images", "list"], env=_env(base_url))
    assert result.exit_code == 0
    assert "No warm runtime configurations found." in result.output


def test_save_from_file_then_list(fake_api, tmp_path):
    base_url, _ = fake_api
    cfg = tmp_path / "php.json"
    cfg.write_text(json.dumps(CONFIG_BODY))
    runner = CliRunner()

    saved = runner.invoke(
        main, ["images", "save", "php-web", "-f", str(cfg)], env=_env(base_url)
    )
    assert saved.exit_code == 0, saved.output
    assert "Saved php-web" in saved.output

    listed = runner.invoke(main, ["images", "list"], env=_env(base_url))
    assert "php-web" in listed.output
    assert "db" in listed.output


def test_save_override_image_and_count(fake_api, tmp_path):
    base_url, state = fake_api
    cfg = tmp_path / "base.json"
    cfg.write_text(json.dumps(CONFIG_BODY))
    result = CliRunner().invoke(
        main,
        [
            "images",
            "save",
            "php-web",
            "-f",
            str(cfg),
            "--image",
            "ghcr.io/your-org/openhands-php:8.4-v2",
            "--count",
            "3",
        ],
        env=_env(base_url),
    )
    assert result.exit_code == 0, result.output
    assert state.configs["php-web"]["image"].endswith(":8.4-v2")
    assert state.configs["php-web"]["count"] == 3


def test_save_missing_required_field_fails(fake_api, tmp_path):
    base_url, _ = fake_api
    cfg = tmp_path / "bad.json"
    cfg.write_text(json.dumps({"image": "ghcr.io/x:1"}))  # no working_dir/command/env
    result = CliRunner().invoke(
        main, ["images", "save", "x", "-f", str(cfg)], env=_env(base_url)
    )
    assert result.exit_code != 0
    assert "missing required field" in result.output


def test_save_from_stdin(fake_api):
    base_url, _ = fake_api
    result = CliRunner().invoke(
        main,
        ["images", "save", "php-web", "-f", "-"],
        input=json.dumps(CONFIG_BODY),
        env=_env(base_url),
    )
    assert result.exit_code == 0, result.output
    assert "Saved php-web" in result.output


def test_get_json_output(fake_api, tmp_path):
    base_url, _ = fake_api
    cfg = tmp_path / "php.json"
    cfg.write_text(json.dumps(CONFIG_BODY))
    runner = CliRunner()
    runner.invoke(
        main, ["images", "save", "php-web", "-f", str(cfg)], env=_env(base_url)
    )
    result = runner.invoke(
        main, ["images", "get", "php-web", "--json"], env=_env(base_url)
    )
    assert result.exit_code == 0
    parsed = json.loads(result.output)
    assert parsed["name"] == "php-web"
    assert parsed["source"] == "db"


def test_get_missing_fails(fake_api):
    base_url, _ = fake_api
    result = CliRunner().invoke(
        main, ["images", "get", "nope"], env=_env(base_url)
    )
    assert result.exit_code != 0
    assert "No configuration named" in result.output


def test_delete_with_yes(fake_api, tmp_path):
    base_url, _ = fake_api
    cfg = tmp_path / "php.json"
    cfg.write_text(json.dumps(CONFIG_BODY))
    runner = CliRunner()
    runner.invoke(
        main, ["images", "save", "php-web", "-f", str(cfg)], env=_env(base_url)
    )
    result = runner.invoke(
        main, ["images", "delete", "php-web", "--yes"], env=_env(base_url)
    )
    assert result.exit_code == 0
    assert "deleted successfully" in result.output


def test_missing_url_is_usage_error(fake_api):
    # No URL in env or options.
    result = CliRunner().invoke(main, ["images", "list"], env={})
    assert result.exit_code != 0
    assert "No Runtime API URL configured" in result.output

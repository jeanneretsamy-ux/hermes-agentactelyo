"""Real config/profile writers and loaders; no provider or model responses mocked."""
from pathlib import Path

from hermes_cli import config, profiles
from hermes_cli.actelyo_defaults import actelyo_local_model_seed
from hermes_cli.config_effective import load_user_config_effective
from hermes_constants import set_hermes_home_override, reset_hermes_home_override


def scoped_config(home):
    token = set_hermes_home_override(home)
    try:
        return config.load_config(), load_user_config_effective()
    finally:
        reset_hermes_home_override(token)


def test_installer_template_and_profile_a_b_a(tmp_path, monkeypatch):
    home = tmp_path / "law-home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_PROFILE", raising=False)
    template = Path(__file__).resolve().parents[2] / "cli-config.yaml.example"
    assert config.seed_config_file(home / "config.yaml", template=template)
    default_model = actelyo_local_model_seed()["model"]
    a, effective_a = scoped_config(home)
    assert a["model"] == effective_a["model"] == default_model
    assert default_model["default"] == "" and "api_key" not in default_model

    other = profiles.create_profile("fixture-beta", no_alias=True, no_skills=True)
    assert other.is_relative_to(home)
    selected = {"model": {"provider": "openrouter", "base_url": "https://openrouter.ai/api/v1",
                          "default": "personal-model"},
                "mcp_servers": {"fixture-rag": {"url": "http://127.0.0.1:3099/mcp"}}}
    current = config.read_user_config_raw(other / "config.yaml")
    current.update(selected)
    config.atomic_config_write(other / "config.yaml", current)
    credential_file = other / ".env"
    credential_file.write_text("OPENROUTER_API_KEY=fictional-qa-key\n", encoding="utf-8")
    before_config = (other / "config.yaml").read_bytes()
    before_credentials = credential_file.read_bytes()
    for target, expected in ((home, default_model), (other, selected["model"]),
                             (home, default_model), (other, selected["model"]), (home, default_model)):
        loaded, effective = scoped_config(target)
        assert loaded["model"] == effective["model"] == expected
    assert (other / "config.yaml").read_bytes() == before_config
    assert credential_file.read_bytes() == before_credentials
    profiles._seed_model_config(other)  # Must never reseed an existing profile.
    assert (other / "config.yaml").read_bytes() == before_config
    assert load_user_config_effective(other / "config.yaml")["mcp_servers"] == selected["mcp_servers"]


def test_fresh_named_profile_without_launch_model(tmp_path, monkeypatch):
    home = tmp_path / "empty-launch-home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_PROFILE", raising=False)
    created = profiles.create_profile("fixture-local", no_alias=True, no_skills=True)
    assert created.is_relative_to(home)
    assert load_user_config_effective(created / "config.yaml")["model"] == actelyo_local_model_seed()["model"]


def test_cloud_launch_selection_still_seeds_independent_profile(tmp_path, monkeypatch):
    home = tmp_path / "selected-launch-home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_PROFILE", raising=False)
    selected = {"model": {"provider": "custom-gateway", "default": "personal-model"},
                "providers": {"custom-gateway": {"base_url": "http://127.0.0.1:15555/v1"}}}
    config.atomic_config_write(home / "config.yaml", selected)
    created = profiles.create_profile("fixture-inherit-choice", no_alias=True, no_skills=True)
    actual = load_user_config_effective(created / "config.yaml")
    assert actual["model"] == selected["model"]
    assert actual["providers"] == selected["providers"]
    current = config.read_user_config_raw(home / "config.yaml")
    current["model"]["default"] = "changed-parent"
    config.atomic_config_write(home / "config.yaml", current)
    assert load_user_config_effective(created / "config.yaml")["model"]["default"] == "personal-model"


def test_installed_profile_resolves_locally_without_borrowing_cloud_key(tmp_path, monkeypatch):
    from hermes_cli.runtime_provider import resolve_runtime_provider
    home = tmp_path / "runtime-home"
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.delenv("HERMES_PROFILE", raising=False)
    monkeypatch.setenv("OPENROUTER_API_KEY", "fictional-cloud-key-must-not-be-used")
    template = Path(__file__).resolve().parents[2] / "cli-config.yaml.example"
    config.seed_config_file(home / "config.yaml", template=template)
    before = (home / "config.yaml").read_bytes()
    runtime = resolve_runtime_provider(requested="custom")
    assert runtime["provider"] == "custom"
    assert runtime["base_url"] == "http://127.0.0.1:1235/v1"
    # The bare-custom SDK uses an internal placeholder, never a user's cloud key.
    assert runtime["api_key"] == "no-key-required"
    assert runtime["api_mode"] == "chat_completions"
    assert config.load_config()["model"]["default"] == ""
    assert (home / "config.yaml").read_bytes() == before

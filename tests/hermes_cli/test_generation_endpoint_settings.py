"""Generation settings travel through real provider storage and runtime resolution."""
from pathlib import Path

import pytest


def test_sampling_contract_rejects_unknown_or_unsupported_values():
    from hermes_cli.generation_settings import generation_parameters
    for raw in ({"temperature": True}, {"temperature": float("nan")}, {"topP": 0}, {"maxOutputTokens": 0}, {"seed": -1}, {"topK": 1.5}, {"api_key": "not-allowed"}):
        with pytest.raises(ValueError):
            generation_parameters(raw, "llama.cpp")
    with pytest.raises(ValueError):
        generation_parameters({"topK": 40}, "openai-compatible")
    assert generation_parameters({}, "llama.cpp") == {}


def test_saved_endpoint_sampling_is_profile_scoped_and_reaches_real_runtime(tmp_path, monkeypatch):
    from hermes_cli.config import load_config, save_config
    from hermes_cli.web_models import CustomEndpointUpdate, CurrentGenerationUpdate
    from hermes_cli.web_routers.config_env import _write_custom_endpoint, _custom_endpoint_response, current_generation, update_current_generation
    from hermes_cli.runtime_provider import resolve_runtime_provider

    monkeypatch.setattr(Path, "home", lambda: tmp_path / "user")
    homes = [tmp_path / "a", tmp_path / "b"]
    for home, temperature in zip(homes, (0.2, 0.8)):
        home.mkdir()
        (home / ".env").write_text("", encoding="utf-8")
        monkeypatch.setenv("HERMES_HOME", str(home))
        cfg = load_config()
        cfg["model"] = {"default": "QA_LOCAL", "provider": "custom:local", "base_url": "http://127.0.0.1:12345/v1"}
        _write_custom_endpoint(cfg, CustomEndpointUpdate(id="local", name="Local", base_url="http://127.0.0.1:12345/v1", model="QA_LOCAL", api_mode="chat_completions", generation_adapter="llama.cpp", generation_settings={"temperature": temperature, "topK": 32, "maxOutputTokens": 64, "thinking": False}))
        save_config(cfg)
    for home, temperature in ((homes[0], 0.2), (homes[1], 0.8), (homes[0], 0.2)):
        monkeypatch.setenv("HERMES_HOME", str(home))
        cfg = load_config()
        endpoint = next(item for item in _custom_endpoint_response(cfg)["endpoints"] if item["id"] == "local")
        assert endpoint["generation_settings"]["temperature"] == temperature
        runtime = resolve_runtime_provider(requested="custom:local", target_model="QA_LOCAL")
        assert runtime["request_overrides"]["extra_body"] == {"temperature": temperature, "top_k": 32, "max_tokens": 64, "chat_template_kwargs": {"enable_thinking": False}}

    before = load_config()["providers"]
    current = current_generation()
    assert current["contract"] == 1 and current["endpoint_id"] == "local"
    assert "api_key" not in current and "base_url" not in current
    result = update_current_generation(CurrentGenerationUpdate(expected_revision=current["revision"], endpoint_id="local", generation_adapter="llama.cpp", generation_settings={"temperature": 0.35, "thinking": False}))
    assert result["generation_settings"] == {"temperature": 0.35, "thinking": False}
    after = load_config()["providers"]
    assert after["local"]["base_url"] == before["local"]["base_url"]
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as failure:
        update_current_generation(CurrentGenerationUpdate(expected_revision=current["revision"], endpoint_id="stale", generation_adapter="llama.cpp", generation_settings={}))
    assert failure.value.status_code == 409
    reset = update_current_generation(CurrentGenerationUpdate(expected_revision=result["revision"], endpoint_id="local", generation_adapter="llama.cpp", generation_settings={}))
    assert reset["generation_settings"] == {}

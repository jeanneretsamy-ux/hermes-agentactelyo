import asyncio
import json
import time

from hermes_constants import get_hermes_home, reset_hermes_home_override, set_hermes_home_override
from tools import actelyo_studio
from tools.registry import registry


def test_registry_dispatches_async_and_rejects_unknown_action():
    result = json.loads(registry.dispatch("actelyo_studio", {"action": "unsupported"}))
    assert result["success"] is False
    assert "inconnue" in result["error"]


def test_runtime_install_worker_inherits_agent_profile(tmp_path, monkeypatch):
    from hermes_cli.web_routers import local_models as service
    homes_seen = []
    monkeypatch.setattr(service, "_runtime_target", lambda backend: ("test-tag", "cpu"))
    monkeypatch.setattr(service.binaries, "installed_engine", lambda _backend: None)
    monkeypatch.setattr(service.bootstrap, "get_supervisor", lambda: None)
    monkeypatch.setattr(service, "_install_engine_job", lambda *_: homes_seen.append(get_hermes_home()))
    home = tmp_path / "agent-profile"
    home.mkdir()
    token = set_hermes_home_override(home)
    try:
        result = json.loads(registry.dispatch("actelyo_studio", {"action": "install_runtime"}))
        assert result["success"]
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            job = json.loads(registry.dispatch("actelyo_studio", {"action": "job", "job_id": result["data"]["job_id"]}))
            if job["data"]["status"] in ("done", "error"):
                break
            time.sleep(.05)
        assert job["data"]["status"] == "done", job
        assert homes_seen == [home]
    finally:
        reset_hermes_home_override(token)


def test_import_is_visible_to_shared_service_and_profile_jobs_are_isolated(tmp_path, monkeypatch):
    from hermes_cli.web_routers import local_models as service

    models = tmp_path / "models"
    models.mkdir()
    source = tmp_path / "example.gguf"
    source.write_bytes(b"GGUF\x00\x00\x00\x00")
    # No real model execution. Keep filesystem staging, config writes, jobs and scope real.
    monkeypatch.setattr(service.bootstrap, "models_dir", lambda: models)
    monkeypatch.setattr(service, "_refresh_runtime", lambda *_: None)
    monkeypatch.setattr(service, "_ensure_server", lambda *_args, **_kw: None)
    monkeypatch.setattr(service.bootstrap, "staged_model_ids", lambda: [p.stem for p in models.glob('*.gguf')])
    assigned = []
    monkeypatch.setattr(service, "_assign_default", lambda _job, model: assigned.append((get_hermes_home(), model)))
    homes = [tmp_path / "profile-a", tmp_path / "profile-b"]
    for home in homes:
        home.mkdir()
        (home / "config.yaml").write_text("local_runtime:\n  enabled: false\n", encoding="utf-8")
    token = set_hermes_home_override(homes[0])
    try:
        imported = json.loads(asyncio.run(actelyo_studio.handle_studio({"action": "import", "path": str(source)})))
        assert imported["success"] and (models / source.name).read_bytes() == source.read_bytes()
        result = json.loads(asyncio.run(actelyo_studio.handle_studio({"action": "activate", "model_id": "example"})))
        assert result["success"]
        job_id = result["data"]["job_id"]
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            job = json.loads(asyncio.run(actelyo_studio.handle_studio({"action": "job", "job_id": job_id})))
            if job["data"]["status"] in ("done", "error"):
                break
            time.sleep(.05)
        assert job["data"]["status"] == "done", job
        assert assigned == [(homes[0], "example")]
        assert service.config_mod.load_config_readonly()["local_runtime"]["enabled"] is True
        other = set_hermes_home_override(homes[1])
        try:
            assert service.config_mod.load_config_readonly()["local_runtime"]["enabled"] is False
            denied = json.loads(asyncio.run(actelyo_studio.handle_studio({"action": "job", "job_id": job_id})))
            assert denied["success"] is False
        finally:
            reset_hermes_home_override(other)
        assert json.loads(asyncio.run(actelyo_studio.handle_studio({"action": "job", "job_id": job_id})))["success"]
    finally:
        reset_hermes_home_override(token)

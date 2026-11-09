"""Exercise real identity seeding/migration and the prompt loader across profiles."""
import pytest

from agent.prompt_builder import load_soul_md
from hermes_cli.config import _ensure_default_soul_md
from hermes_cli.default_soul import DEFAULT_SOUL_MD, _PRE_COPILOT_DEFAULT_SOUL_MD


@pytest.mark.parametrize("windows_text", [False, True])
def test_copilot_default_upgrades_only_unmodified_identity_across_profiles(tmp_path, monkeypatch, windows_text):
    alpha, beta = tmp_path / "alpha", tmp_path / "beta"
    for home in (alpha, beta):
        home.mkdir()
        (home / "config.yaml").write_text("model: cabinet-existing-model\n", encoding="utf8")
    old = _PRE_COPILOT_DEFAULT_SOUL_MD
    if windows_text:
        old = "\ufeff" + old.replace("\u2014", "--").replace("\n", "\r\n") + "\r\n"
    (alpha / "SOUL.md").write_bytes(old.encode("utf8"))
    customized = _PRE_COPILOT_DEFAULT_SOUL_MD + "\nUser instruction: use my approved firm templates."
    (beta / "SOUL.md").write_text(customized, encoding="utf8")
    original_beta = (beta / "SOUL.md").read_bytes()
    configs = {home: (home / "config.yaml").read_bytes() for home in (alpha, beta)}

    # Ambient home deliberately points to the other profile. Neither migration
    # nor prompt loading may silently substitute its identity or provider.
    for home in (alpha, beta, alpha):
        monkeypatch.setenv("HERMES_HOME", str(beta if home == alpha else alpha))
        _ensure_default_soul_md(home)
        expected = DEFAULT_SOUL_MD if home == alpha else customized
        assert load_soul_md(home_override=home) == expected

    assert (beta / "SOUL.md").read_bytes() == original_beta
    assert all((home / "config.yaml").read_bytes() == content for home, content in configs.items())


def test_new_copilot_identity_is_loaded_by_real_prompt_loader(tmp_path):
    home = tmp_path / "fresh"
    home.mkdir()
    _ensure_default_soul_md(home)
    assert load_soul_md(home_override=home) == DEFAULT_SOUL_MD
    # Repeated first-run initialization preserves the actual file and identity.
    before = (home / "SOUL.md").stat().st_mtime_ns
    _ensure_default_soul_md(home)
    assert (home / "SOUL.md").stat().st_mtime_ns == before

"""The built-in and seeded identity agree; custom profile personas stay independent."""
from types import SimpleNamespace

from agent.prompt_builder import DEFAULT_AGENT_IDENTITY
from agent.system_prompt import _identity_parts
from hermes_cli.default_soul import DEFAULT_SOUL_MD, is_legacy_template_soul


def test_default_and_seeded_persona_use_the_same_identity(tmp_path, monkeypatch):
    monkeypatch.setenv('HERMES_HOME', str(tmp_path))
    agent = SimpleNamespace(load_soul_identity=False, skip_context_files=True, _session_db=None)
    parts, loaded = _identity_parts(agent, 8192)
    assert not loaded
    assert parts == [DEFAULT_SOUL_MD]
    assert DEFAULT_AGENT_IDENTITY == DEFAULT_SOUL_MD
    assert not is_legacy_template_soul('You are my personally configured assistant.')


def test_profile_identity_is_scoped_and_does_not_mutate_default(tmp_path, monkeypatch):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(); b.mkdir()
    (a / 'SOUL.md').write_text(DEFAULT_SOUL_MD, encoding='utf-8')
    custom = 'Actelyo specialist for the second user. Answer in French.'
    (b / 'SOUL.md').write_text(custom, encoding='utf-8')
    monkeypatch.setenv('HERMES_HOME', str(a))
    agent = SimpleNamespace(load_soul_identity=True, skip_context_files=True,
                            _session_db=SimpleNamespace(db_path=str(a / 'state.db')))
    before, loaded = _identity_parts(agent, 8192)
    assert loaded and before == [DEFAULT_SOUL_MD]
    agent._session_db.db_path = str(b / 'state.db')
    assert _identity_parts(agent, 8192) == ([custom], True)
    agent._session_db.db_path = str(a / 'state.db')
    assert _identity_parts(agent, 8192) == (before, True)

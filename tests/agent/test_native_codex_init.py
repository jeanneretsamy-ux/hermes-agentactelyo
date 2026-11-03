"""Native transport authentication must remain owned by the native CLI."""
from types import SimpleNamespace


def test_native_agent_initializes_without_an_http_credential(monkeypatch):
    from agent import agent_init
    from run_agent import AIAgent

    def unexpected_http_route(*args, **kwargs):
        raise AssertionError('A native CLI session must not resolve an HTTP credential')

    monkeypatch.setattr(agent_init, '_routed_client_kwargs', unexpected_http_route)
    agent = AIAgent(provider='openai-codex', api_mode='codex_app_server', model='native-test-model',
                    quiet_mode=True, skip_memory=True, skip_context_files=True, skip_background_review=True,
                    enabled_toolsets=[])
    try:
        assert agent.api_mode == 'codex_app_server'
        assert agent.client is None
        assert agent._client_kwargs == {}
        assert agent._primary_runtime['api_mode'] == 'codex_app_server'
    finally:
        agent.close()


def test_http_mode_still_constructs_the_http_client(monkeypatch):
    from agent import agent_init

    calls = []
    monkeypatch.setattr(agent_init, '_init_openai_client', lambda *args: calls.append(args))
    agent = SimpleNamespace(provider='openai-codex', model='test', api_mode='codex_responses')
    agent_init._build_client(agent, None, None, None)
    assert calls and calls[0][0] is agent

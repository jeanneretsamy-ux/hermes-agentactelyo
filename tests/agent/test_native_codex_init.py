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


def test_native_workspace_policy_reaches_the_real_protocol_boundary(tmp_path):
    from agent.transports.codex_app_server_session import CodexAppServerSession

    class WireClient:
        def __init__(self, **kwargs): self.requests = []
        def initialize(self, **kwargs): return {}
        def request(self, method, params=None, timeout=None):
            self.requests.append((method, params))
            return {'thread': {'id': 'policy-test'}}
        def close(self): pass

    for profile, expected in (('workspace-write', 'workspace-write'), ('read-only-with-approval', 'read-only')):
        client = WireClient()
        session = CodexAppServerSession(cwd=str(tmp_path), permission_profile=profile, client_factory=lambda **kw: client)
        try:
            session.ensure_started()
            starts = [params for method, params in client.requests if method == 'thread/start']
            assert starts[0]['sandbox'] == expected
            assert starts[0]['approvalPolicy'] == 'on-request'
            assert starts[0]['cwd'] == str(tmp_path)
        finally:
            session.close()

"""Exercise real RPC registration, contracts and A→B→A profile isolation."""
import os

from hermes_cli import atelier
from hermes_constants import reset_hermes_home_override, set_hermes_home_override
from tui_gateway import server
from tui_gateway.contracts.registry import METHODS


def call(method, **params):
    contract = METHODS[method]
    response = server._methods[method](1, contract.params.model_validate(params).model_dump())
    assert 'error' not in response, response
    contract.result.model_validate(response['result'])
    return response['result']


def test_atelier_profiles_a_b_a_and_missing_revision(monkeypatch, tmp_path):
    homes = {name: tmp_path / name for name in ('default', 'atelier-b')}
    for home in homes.values(): home.mkdir()
    monkeypatch.setattr('hermes_cli.profiles.get_profile_dir', lambda name: homes[name])
    monkeypatch.setattr(server, '_hermes_home', homes['default'])
    env_before = dict(os.environ)
    token = set_hermes_home_override(homes['default'])
    try:
        sources = [{'id': 's', 'name': 'piece.txt', 'url': 'file:///piece.txt', 'text': 'Signé le 15 octobre 2026.'}]
        pid = next(iter(atelier.source_catalog(sources)))
        panel = atelier.save({'schema_version': 1, 'id': 'chrono', 'name': 'Chronologie A', 'kind': 'chronology',
                              'sources': sources, 'events': [{'id': 's', 'title': 'Signature', 'date': '2026-10-15', 'passage_ids': [pid]}]})
        assert call('atelier.list', profile='default')['revisions'][0]['revision'] == panel['revision']
        assert call('atelier.list', profile='atelier-b')['revisions'] == []
        missing = server._methods['atelier.activate'](1, {'profile': 'atelier-b', 'revision': panel['revision']})
        assert missing['error']['code'] == 5064
        assert call('atelier.preview', profile='default', revision=panel['revision'])['events'][0]['evidence'][0]['quote'] == sources[0]['text']
        assert call('atelier.activate', profile='default', revision=panel['revision'])['revisions'][0]['active']
        assert call('atelier.list', profile='atelier-b')['revisions'] == []
        assert call('atelier.list', profile='default')['revisions'][0]['active']
        assert not call('atelier.deactivate', profile='default', panel_id=panel['id'])['revisions'][0]['active']
        assert dict(os.environ) == env_before
    finally:
        reset_hermes_home_override(token)

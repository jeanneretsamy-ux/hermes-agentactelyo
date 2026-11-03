"""Actual CLI/storage round trips, immutable references and revision changes."""
from copy import deepcopy
import json
import sqlite3

import pytest

from hermes_cli import atelier
from hermes_constants import reset_hermes_home_override, set_hermes_home_override


@pytest.fixture
def bundle():
    sources = [{'id': 'bail', 'name': 'bail.txt', 'url': 'file:///dossier/bail.txt', 'page': 3,
                'text': "Le bail est signé le 15 octobre 2026.\nLa prise d'effet est le 01/11/2026."}]
    catalog = atelier.source_catalog(sources)
    return {'schema_version': 1, 'id': 'chronologie-alpha', 'name': 'Dossier ALPHA', 'kind': 'chronology',
            'sources': sources, 'events': [
                {'id': 'effet', 'date': '2026-11-01', 'title': "Prise d'effet", 'passage_ids': [list(catalog)[1]]},
                {'id': 'signature', 'date': '2026-10-15', 'title': 'Signature du bail', 'passage_ids': [list(catalog)[0]]}]}


def test_cli_draft_preview_activation_and_rollback(tmp_path, bundle, capsys):
    token = set_hermes_home_override(tmp_path)
    try:
        path = tmp_path / 'bundle.json'
        path.write_text(json.dumps(bundle), encoding='utf-8')
        assert atelier.main(['save', str(path)]) == 0
        saved = json.loads(capsys.readouterr().out)
        assert not any(r['active'] for r in atelier.snapshot()['revisions'])
        first = atelier.preview(saved['revision'])
        assert [e['id'] for e in first['events']] == ['signature', 'effet']
        citation = first['events'][0]['evidence'][0]
        assert citation['quote'] == bundle['sources'][0]['text'][citation['start']:citation['end']]
        assert citation['page'] == 3
        assert first['semantic_review'] == 'human_required'
        atelier.activate(first['revision'])
        bundle['name'] = 'Chronologie révisée'
        second = atelier.save(bundle)
        atelier.save(bundle)  # content-addressed, repeated save is idempotent
        assert len(atelier.snapshot()['revisions']) == 2
        atelier.activate(second['revision'])
        assert [r['revision'] for r in atelier.snapshot()['revisions'] if r['active']] == [second['revision']]
        atelier.activate(first['revision'])
        assert [r['revision'] for r in atelier.snapshot()['revisions'] if r['active']] == [first['revision']]
        atelier.deactivate(first['id'])
        assert not any(r['active'] for r in atelier.snapshot()['revisions'])
        assert len(atelier.snapshot()['revisions']) == 2
    finally:
        reset_hermes_home_override(token)


@pytest.mark.parametrize('change', ['unknown_passage', 'changed_text', 'wrong_date', 'invalid_date', 'extra_code', 'duplicate_source', 'duplicate_event'])
def test_invalid_extensions_never_enter_store(tmp_path, bundle, change):
    if change == 'unknown_passage': bundle['events'][0]['passage_ids'] = ['p_invented']
    elif change == 'changed_text': bundle['sources'][0]['text'] += ' Modification.'
    elif change == 'wrong_date': bundle['events'][0]['date'] = '2027-01-01'
    elif change == 'invalid_date': bundle['events'][0]['date'] = '2026-02-30'
    elif change == 'extra_code': bundle['script'] = 'alert(1)'
    elif change == 'duplicate_source': bundle['sources'].append(deepcopy(bundle['sources'][0]))
    else: bundle['events'].append(deepcopy(bundle['events'][0]))
    token = set_hermes_home_override(tmp_path)
    try:
        with pytest.raises(ValueError): atelier.save(bundle)
        assert atelier.snapshot()['revisions'] == []
    finally:
        reset_hermes_home_override(token)


def test_storage_tamper_refuses_preview_and_activation(tmp_path, bundle):
    token = set_hermes_home_override(tmp_path)
    try:
        panel = atelier.save(bundle)
        bundle['events'][0]['title'] = 'Titre modifié hors version'
        with sqlite3.connect(tmp_path / 'atelier.sqlite3') as conn:
            conn.execute('UPDATE revisions SET bundle=?', (json.dumps(bundle),))
        with pytest.raises(ValueError, match='changé'): atelier.preview(panel['revision'])
        with pytest.raises(ValueError): atelier.activate(panel['revision'])
        assert not any(r['active'] for r in atelier.snapshot()['revisions'])
    finally:
        reset_hermes_home_override(token)


def test_csv_row_date_and_columns_survive_assembly(bundle):
    bundle['sources'] = [{'id': 'table', 'name': 'echeances.csv', 'url': 'file:///echeances.csv',
                         'text': 'Dossier;Date;Montant\nALPHA;15/10/2026;2500\nBETA;15/11/2026;9000'}]
    catalog = atelier.source_catalog(bundle['sources'])
    bundle['events'] = [{'id': 'echeance', 'date': '2026-10-15', 'title': 'Échéance ALPHA', 'passage_ids': [list(catalog)[0]]}]
    panel = atelier.validate_bundle(bundle)
    evidence = panel['events'][0]['evidence'][0]
    assert evidence['table']['headers'] == ['Dossier', 'Date', 'Montant']
    assert evidence['quote'] == 'ALPHA;15/10/2026;2500'
    assert evidence['page'] is None

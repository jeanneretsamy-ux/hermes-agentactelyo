import pytest
from hermes_cli import projects_db as pdb, legal_practice as legal


def test_workflow_dates_retries_and_project_boundary(tmp_path):
    with pdb.connect_closing(db_path=tmp_path / 'projects.db') as conn:
        a = pdb.create_project(conn, name='A', folders=[str(tmp_path)])
        b = pdb.create_project(conn, name='B', folders=[])
        legal.initialize_legal(conn)
        def write(action, **params):
            return legal.legal_mutate(conn, a, action, params)
        write('workspace.set', domain='societes')
        client = write('client.save', name='Client')['clients'][0]
        matter_type = legal.legal_snapshot(conn,a)['matter_types'][0]
        matter = write('matter.save', client_id=client['id'],title='Société',matter_type=matter_type)['matters'][0]
        first = legal.legal_snapshot(conn,a)['tasks']
        assert first
        assert any('Statuts' in task['title'] for task in first)
        assert write('workflow.apply', matter_id=matter['id'])['tasks'] == first
        task = first[0]
        updated = write('task.save',id=task['id'],matter_id=matter['id'],title='Vérification',due_on='2020-01-02',remind_on='2020-01-01')['tasks']
        assert next(t for t in updated if t['id']==task['id'])['alert']=='overdue'
        write('workflow.apply',matter_id=matter['id'])
        assert next(t for t in legal.legal_snapshot(conn,a)['tasks'] if t['id']==task['id'])['title']=='Vérification'
        with pytest.raises(ValueError):
            legal.legal_mutate(conn,b,'task.save',dict(id=task['id'],matter_id=matter['id'],title='Intrusion'))
        with pytest.raises(ValueError):
            write('task.save',matter_id=matter['id'],title='Invalide',due_on='2026-01-01',remind_on='2026-01-02')
        assert legal.legal_snapshot(conn,b)['tasks']==[]
        done = write('task.save',id=task['id'],matter_id=matter['id'],title='Vérification',due_on='2020-01-02',task_status='done')['tasks']
        assert next(t for t in done if t['id']==task['id'])['alert']==''


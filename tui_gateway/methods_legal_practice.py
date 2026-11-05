"""Profile-scoped legal practice RPCs. No provider calls or external financial operations."""
from .method_ctx import HandlerRegistry, bind_module

_registry = HandlerRegistry()


@_registry.method("legal.catalog")
@_registry.profile_scoped
def legal_catalog(rid, params):
    from hermes_cli import legal_practice as legal, projects_db as pdb, legal_workflow

    try:
        with pdb.connect_closing() as conn:
            legal.initialize_legal(conn)
            rows = conn.execute("""SELECT p.id, p.name, w.domain FROM projects p
                LEFT JOIN legal_workspaces w ON w.project_id=p.id
                WHERE p.archived=0 ORDER BY p.name, p.id""").fetchall()
            return _ok(rid, {"domains": list(legal.LEGAL_DOMAINS),
                              "workspaces": [{**dict(row), "due_tasks": sum(bool(t["alert"]) for t in legal_workflow.rows(conn, row["id"]))} for row in rows]})
    except Exception as error:
        return _err(rid, 5061, str(error))


def _register_legal_method(action):
    @_registry.method(f"legal.{action}")
    @_registry.profile_scoped
    def handler(rid, params):
        from hermes_cli import legal_practice as legal, projects_db as pdb

        try:
            from tui_gateway.contracts.registry import METHODS
            params=METHODS['legal.'+action].params.model_validate(params).model_dump()
            with pdb.connect_closing() as conn:
                project = pdb.get_project(conn, params.get("project_id", ""))
                if project is None:
                    return _err(rid, 5062, "no such project")
                legal.initialize_legal(conn)
                from hermes_cli.legal_finance_files import TRANSFERS, transfer
                if action in TRANSFERS:
                    return _ok(rid,transfer(conn,project.id,action,params))
                if action=='finance.prepare':
                    from tui_gateway.contracts.registry import METHODS
                    operation=params['action']
                    from hermes_cli.legal_operations import HANDLERS
                    if operation not in HANDLERS and operation not in ('fee.add','finance.budget.save','finance.fee.review','document.create','payment.add'):
                        raise ValueError('Opération de préparation non autorisée.')
                    if any(k in params['payload'] for k in ('project_id','profile','request_id')):
                        raise ValueError('Le périmètre et la clé de requête sont définis par la préparation.')
                    normalized=METHODS['legal.'+operation].params.model_validate({**params['payload'],'project_id':project.id,'request_id':params['request_id']}).model_dump(exclude={'profile','project_id'})
                    conn.execute('SAVEPOINT finance_preview')
                    try:
                        legal._legal_apply(conn,project.id,operation,normalized)
                    finally:
                        conn.execute('ROLLBACK TO finance_preview')
                        conn.execute('RELEASE finance_preview')
                    return _ok(rid,{'project_id':project.id,'action':operation,'params':normalized,'description':'Préparation '+operation+' : aucune donnée financière enregistrée avant confirmation.'})
                if action in ('finance.snapshot','finance.export'):
                    from hermes_cli import legal_finance
                    reader={'finance.snapshot':legal_finance.snapshot,'finance.export':legal_finance.export_csv}[action]
                    return _ok(rid,reader(conn,project.id))
                result = (legal.legal_snapshot(conn, project.id) if action == "snapshot"
                          else legal.legal_mutate(conn, project.id, action, params))
                return _ok(rid, result)
        except ValueError as error:
            return _err(rid, 5063, str(error))
        except Exception as error:
            return _err(rid, 5061, str(error))


for _file_action in ('finance.file.start','finance.file.chunk','finance.file.finish','finance.file.cancel','finance.file.read','finance.file.text'):
    _register_legal_method(_file_action)


for _legal_action in (
    'business.party.save','business.contract.save','business.purchase.save',
    'business.purchase.transition','business.supplier_payment.add','finance.timer.start','finance.timer.change','finance.file.extract','finance.file.stamp','finance.billing_order.create','finance.billing_order.invoice','finance.billing_order.cancel','finance.fec.import','finance.objective.save','finance.forecast.save','finance.mileage.add','finance.reminder.prepare',
    'finance.snapshot','finance.export','finance.prepare','finance.budget.save','finance.fee.review',
    "task.save", "workflow.apply", "snapshot", "workspace.set", "firm.settings.set", "client.save", "matter.save", "act.save", "library.import",
    "fee.add", "fee_code.save", "subscription.save", "subscription.invoice",
    "practice_document.create", "document.create", "document.credit",
    "payment.add", "payment.allocate",
):
    _register_legal_method(_legal_action)


def register(server):
    bind_module(globals(), server)

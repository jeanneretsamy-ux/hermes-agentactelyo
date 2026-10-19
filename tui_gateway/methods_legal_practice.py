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
            with pdb.connect_closing() as conn:
                project = pdb.get_project(conn, params.get("project_id", ""))
                if project is None:
                    return _err(rid, 5062, "no such project")
                legal.initialize_legal(conn)
                result = (legal.legal_snapshot(conn, project.id) if action == "snapshot"
                          else legal.legal_mutate(conn, project.id, action, params))
                return _ok(rid, result)
        except ValueError as error:
            return _err(rid, 5063, str(error))
        except Exception as error:
            return _err(rid, 5061, str(error))


for _legal_action in (
    "task.save", "workflow.apply", "snapshot", "workspace.set", "firm.settings.set", "client.save", "matter.save", "act.save", "library.import",
    "fee.add", "fee_code.save", "subscription.save", "subscription.invoice",
    "practice_document.create", "document.create", "document.credit",
    "payment.add", "payment.allocate",
):
    _register_legal_method(_legal_action)


def register(server):
    bind_module(globals(), server)

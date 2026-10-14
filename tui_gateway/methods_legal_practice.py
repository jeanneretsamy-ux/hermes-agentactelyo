"""Profile-scoped legal practice RPCs. No provider calls or external financial operations."""
from .method_ctx import HandlerRegistry, bind_module

_registry = HandlerRegistry()


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


for _legal_action in ("snapshot", "workspace.set", "client.save", "matter.save", "act.save", "fee.add", "document.create", "payment.add"):
    _register_legal_method(_legal_action)


def register(server):
    bind_module(globals(), server)

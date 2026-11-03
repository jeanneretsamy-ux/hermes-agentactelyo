"""Atelier persistence follows the same profile scope on every transport."""
from .method_ctx import HandlerRegistry, bind_module

_registry = HandlerRegistry()


def _register_atelier(action):
    @_registry.method(f'atelier.{action}')
    @_registry.profile_scoped
    def handler(rid, params):
        from hermes_cli import atelier
        try:
            if action == 'list':
                result = atelier.snapshot()
            elif action == 'preview':
                result = atelier.preview(params['revision'])
            elif action == 'activate':
                result = atelier.activate(params['revision'])
            else:
                result = atelier.deactivate(params['panel_id'])
            return _ok(rid, result)
        except (ValueError, KeyError) as error:
            return _err(rid, 5064, str(error))
        except Exception:
            return _err(rid, 5065, "Impossible d'accéder à l'Atelier de ce profil.")


for _atelier_action in ('list', 'preview', 'activate', 'deactivate'):
    _register_atelier(_atelier_action)


def register(server):
    bind_module(globals(), server)

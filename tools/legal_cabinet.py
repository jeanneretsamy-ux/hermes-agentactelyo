"""Conversation-facing access to the legal workspace and its internal billing drafts.

The selected Desktop Project is the authority boundary. Monetary operations are
delegated to the same transactional/idempotent domain layer used by the UI.
"""
from __future__ import annotations

import json

from tools.registry import registry


_ACTIONS = (
    "snapshot", "workspace.set", "firm.settings.set", "client.save",
    "matter.save", "act.save", "fee.add", "document.create", "payment.add",
)


def legal_cabinet(action: str, project: str = "", task_id: str | None = None, **values) -> str:
    """Read or update legal workspace records for an explicit or active project."""
    from hermes_cli import legal_practice as legal, projects_db as pdb
    from tools.project_tools import _calling_session_project_id

    try:
        with pdb.connect_closing() as conn:
            project = (project or "").strip()
            if project:
                target = pdb.get_project(conn, project)
                if target is None:
                    # Names are useful in chat and are resolved only within this profile.
                    target = next((p for p in pdb.list_projects(conn, include_archived=True)
                                   if p.name.casefold() == project.casefold()), None)
            else:
                scoped, active_id = _calling_session_project_id(conn, task_id)
                if not scoped:
                    active_id = pdb.get_active_id(conn)
                target = pdb.get_project(conn, active_id) if active_id else None
            if target is None:
                return json.dumps({"success": False, "error": "Aucun projet actif déterminé. Passez project avec le nom, slug ou identifiant visible dans desktop_project(action='list')."}, ensure_ascii=False)
            legal.initialize_legal(conn)
            if action == "snapshot":
                result = legal.legal_snapshot(conn, target.id)
            elif action in _ACTIONS[1:]:
                if action == "firm.settings.set":
                    for key, default in {
                        "jurisdiction": "FR", "vat_regime": "standard", "vat_number": "",
                        "bar_name": "", "payment_delay_days": 30,
                        "late_penalty_rate": "3 fois le taux d’intérêt légal",
                    }.items():
                        values.setdefault(key, default)
                result = legal.legal_mutate(conn, target.id, action, values)
                if action == "document.create" and result["documents"]:
                    result["rendered_document"] = legal.render_legal_document(result["documents"][-1])
            else:
                return json.dumps({"success": False, "error": f"Action inconnue. Actions disponibles : {', '.join(_ACTIONS)}"}, ensure_ascii=False)
            return json.dumps({"success": True, "project": {
                "id": target.id, "slug": target.slug, "name": target.name,
                "primary_path": target.primary_path,
            }, "action": action, "data": result}, ensure_ascii=False)
    except (ValueError, TypeError) as exc:
        return json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"success": False, "error": f"Échec de l’opération du cabinet : {exc}"}, ensure_ascii=False)


registry.register(
    name="legal_cabinet",
    toolset="project",
    schema={
        "name": "legal_cabinet",
        "description": (
            "Manage the legal workspace of a Desktop Project from chat. First use desktop_project(action='list') "
            "when the active project is unclear, then call snapshot before changes. Actions: snapshot; workspace.set "
            "(domain + matter_types); firm.settings.set (FR firm identity); client.save; matter.save; act.save; "
            "fee.add; document.create (quote or invoice working draft; optional template_id: classique, synthese, detaille); payment.add. Pass project as its name, slug, "
            "or id, or omit it to use this session's active project. This creates internal drafts only: never claim "
            "a document was issued, signed, sent, or paid. Use explicit amounts from the user/source records, never guess. "
            "Before drafting, inspect snapshot, search/read the user's local files and supplied examples with the file tools, "
            "and preserve their factual details and requested structure; ask for missing material rather than inventing it. "
            "When asked to use an example, identify it as a reference, compare its structure with the client matter, and replace only fields supported by that matter. "
            "When asked to enrich or revise a section of an act, read the saved act and relevant case facts, change only the named section, preserve accepted clauses and return a concise change summary before saving with act.save. "
            "Do not present generated acts as legally validated; flag missing facts, legal citations and review points. "
            "Identify missing client/cabinet fields. After creating a quote/invoice record, save the returned "
            "rendered_document with write_file under project.primary_path using a clear filename; if primary_path is empty, "
            "ask where to save it. "
            "Label it BROUILLON until reviewed. Monetary writes require a fresh unique request_id."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": list(_ACTIONS)},
                "project": {"type": "string", "description": "Project name, slug, or id; defaults to this session's active project."},
                "domain": {"type": "string", "description": "workspace.set: domain id from snapshot.domains."},
                "matter_types": {"type": "array", "items": {"type": "string"}},
                "jurisdiction": {"type": "string", "enum": ["FR"]},
                "legal_name": {"type": "string"}, "address": {"type": "string"},
                "siren": {"type": "string"}, "vat_number": {"type": "string"},
                "vat_regime": {"type": "string", "enum": ["standard", "franchise"]},
                "bar_name": {"type": "string"}, "payment_delay_days": {"type": "integer"},
                "late_penalty_rate": {"type": "string"},
                "id": {"type": "string"}, "name": {"type": "string"}, "email": {"type": "string"},
                "customer_type": {"type": "string", "enum": ["individual", "professional"]},
                "client_id": {"type": "string"}, "title": {"type": "string"},
                "matter_type": {"type": "string"}, "reference": {"type": "string"},
                "status": {"type": "string", "enum": ["open", "closed"]},
                "act_type": {"type": "string"}, "body": {"type": "string"},
                "request_id": {"type": "string"}, "matter_id": {"type": "string"},
                "description": {"type": "string"}, "kind": {"type": "string", "enum": ["fixed", "time", "quote", "invoice"]},
                "amount_cents": {"type": "integer"}, "minutes": {"type": "integer"},
                "rate_cents": {"type": "integer"}, "tax_bps": {"type": "integer"},
                "responsible_user": {"type": "string"}, "fee_ids": {"type": "array", "items": {"type": "string"}},
                "due_on": {"type": "string"}, "document_id": {"type": "string"},
                "template_id": {"type": "string", "enum": ["classique", "synthese", "detaille"]},
                "paid_on": {"type": "string"},
            },
            "required": ["action"],
        },
    },
    handler=lambda args, **kw: legal_cabinet(
        action=args.get("action", ""), project=args.get("project", ""), task_id=kw.get("task_id"),
        **{key: value for key, value in args.items() if key not in {"action", "project"}},
    ),
)


"""Matter-owned operational steps and explicit dates; never infer statutory deadlines."""
from datetime import date
import secrets


SCHEMA = """
CREATE TABLE IF NOT EXISTS legal_tasks (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 matter_id TEXT NOT NULL REFERENCES legal_matters(id) ON DELETE CASCADE,
 title TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending', due_on TEXT NOT NULL DEFAULT '',
 remind_on TEXT NOT NULL DEFAULT '', responsible_user TEXT NOT NULL DEFAULT '',
 notes TEXT NOT NULL DEFAULT '', template_key TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS legal_task_template ON legal_tasks(matter_id,template_key)
 WHERE template_key != '';
"""


def templates(domain):
    # Domain act types supply concrete deliverables, without inventing legal time limits.
    return [{"id": "intake", "title": "Vérifier les parties, pièces et informations du dossier"},
            {"id": "dates", "title": "Vérifier et saisir les échéances applicables"},
            *[{"id": f"act:{label}", "title": f"Préparer et faire valider : {label}"}
              for label in domain["act_types"]],
            {"id": "close", "title": "Contrôler les formalités, archiver et clôturer"}]


def rows(conn, pid):
    today = date.today().isoformat()
    result = [dict(r) for r in conn.execute(
        "SELECT * FROM legal_tasks WHERE project_id=? ORDER BY due_on='',due_on,rowid", (pid,))]
    for row in result:
        row.pop("project_id")
        row["alert"] = ("overdue" if row["due_on"] and row["due_on"] < today else
                        "due" if row["due_on"] == today else
                        "reminder" if row["remind_on"] and row["remind_on"] <= today else "") if row["status"] == "pending" else ""
    return result


def apply(conn, pid, action, p):
    from hermes_cli.legal_practice import _legal_date, _legal_row, _legal_text, legal_domain
    matter = _legal_row(conn, "legal_matters", pid, p.get("matter_id"))
    if action == "workflow.apply":
        workspace = conn.execute("SELECT domain FROM legal_workspaces WHERE project_id=?", (pid,)).fetchone()
        if not workspace:
            raise ValueError("Choisissez un domaine juridique avant le processus.")
        for step in templates(legal_domain(workspace["domain"])):
            conn.execute("""INSERT OR IGNORE INTO legal_tasks
                (id,project_id,matter_id,title,template_key) VALUES (?,?,?,?,?)""",
                (secrets.token_hex(16), pid, matter["id"], step["title"], step["id"]))
        return
    task_id = p.get("id") or secrets.token_hex(16)
    if p.get("id"):
        old = _legal_row(conn, "legal_tasks", pid, task_id)
        if old["matter_id"] != matter["id"]:
            raise ValueError("Cette étape appartient à un autre dossier.")
    status = p.get("task_status", "pending")
    if status not in ("pending", "done", "cancelled"):
        raise ValueError("État de tâche invalide")
    due = date.fromisoformat(_legal_date(p["due_on"])).isoformat() if p.get("due_on") else ""
    remind = date.fromisoformat(_legal_date(p["remind_on"])).isoformat() if p.get("remind_on") else ""
    if remind and (not due or remind > due):
        raise ValueError("Le rappel doit précéder ou être le jour de l’échéance.")
    title = _legal_text(p.get("title"), required=True)
    conn.execute("""INSERT INTO legal_tasks
        (id,project_id,matter_id,title,status,due_on,remind_on,responsible_user,notes)
        VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
        title=excluded.title,status=excluded.status,due_on=excluded.due_on,
        remind_on=excluded.remind_on,responsible_user=excluded.responsible_user,notes=excluded.notes""",
        (task_id,pid,matter["id"],title,status,due,remind,
         _legal_text(p.get("responsible_user"),limit=200),_legal_text(p.get("notes"),limit=5000)))

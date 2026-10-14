"""Project-owned legal workspaces and internal billing, stored in the profile projects.db.

Documents are working drafts, never fiscal issuance or an external payment operation.
Money is integer cents; fees, documents and payments are idempotent and transactional.
"""
from __future__ import annotations

import json
import secrets
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from hermes_cli.sqlite_util import write_txn


LEGAL_DOMAINS = (
    {"id": "societes", "label": "Droit des sociétés", "matter_types": ["Constitution", "Vie sociale", "Cession de titres", "Restructuration", "Dissolution"], "act_types": ["Statuts", "Procès-verbal d'assemblée", "Pacte d'associés", "Cession de titres"]},
    {"id": "fiscal", "label": "Droit fiscal", "matter_types": ["Conseil fiscal", "Contrôle fiscal", "Réclamation", "Contentieux fiscal"], "act_types": ["Note fiscale", "Réponse à une proposition de rectification", "Réclamation contentieuse"]},
    {"id": "social", "label": "Droit social", "matter_types": ["Embauche", "Relations collectives", "Rupture du contrat", "Contentieux prud'homal"], "act_types": ["Contrat de travail", "Avenant", "Accord collectif", "Conclusions prud'homales"]},
    {"id": "penal", "label": "Droit pénal", "matter_types": ["Défense pénale", "Victime", "Instruction", "Audience", "Exécution des peines"], "act_types": ["Plainte", "Constitution de partie civile", "Demande d'actes", "Conclusions pénales"]},
    {"id": "civil", "label": "Droit civil et famille", "matter_types": ["Responsabilité", "Contrats", "Divorce", "Succession"], "act_types": ["Assignation", "Conclusions", "Protocole d'accord", "Convention"]},
    {"id": "immobilier", "label": "Droit immobilier", "matter_types": ["Bail", "Copropriété", "Construction", "Vente immobilière"], "act_types": ["Bail", "Mise en demeure", "Conclusions", "Protocole transactionnel"]},
    {"id": "commercial", "label": "Droit commercial", "matter_types": ["Contrats commerciaux", "Recouvrement", "Litige commercial", "Entreprise en difficulté"], "act_types": ["Contrat commercial", "Conditions générales", "Mise en demeure", "Assignation"]},
    {"id": "administratif", "label": "Droit administratif", "matter_types": ["Recours", "Marchés publics", "Urbanisme", "Responsabilité administrative"], "act_types": ["Recours gracieux", "Requête", "Mémoire", "Référé"]},
)

_LEGAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS legal_workspaces (
 project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
 domain TEXT NOT NULL, matter_types TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS legal_clients (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 name TEXT NOT NULL, email TEXT NOT NULL, address TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS legal_matters (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 client_id TEXT NOT NULL REFERENCES legal_clients(id), title TEXT NOT NULL,
 matter_type TEXT NOT NULL, reference TEXT NOT NULL, status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS legal_acts (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 title TEXT NOT NULL, act_type TEXT NOT NULL, body TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS legal_fees (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 matter_id TEXT NOT NULL REFERENCES legal_matters(id), description TEXT NOT NULL,
 kind TEXT NOT NULL, minutes INTEGER NOT NULL, rate_cents INTEGER NOT NULL,
 net_cents INTEGER NOT NULL, tax_bps INTEGER NOT NULL, tax_cents INTEGER NOT NULL,
 invoice_id TEXT
);
CREATE TABLE IF NOT EXISTS legal_documents (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 matter_id TEXT NOT NULL REFERENCES legal_matters(id), kind TEXT NOT NULL,
 reference TEXT NOT NULL, created_on TEXT NOT NULL, due_on TEXT NOT NULL,
 snapshot TEXT NOT NULL, net_cents INTEGER NOT NULL, tax_cents INTEGER NOT NULL,
 total_cents INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS legal_payments (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 document_id TEXT NOT NULL REFERENCES legal_documents(id), amount_cents INTEGER NOT NULL,
 paid_on TEXT NOT NULL, reference TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS legal_requests (
 project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 request_id TEXT NOT NULL, payload TEXT NOT NULL, PRIMARY KEY(project_id, request_id)
);
"""


def initialize_legal(conn):
    conn.executescript(_LEGAL_SCHEMA)


def legal_domain(domain_id):
    for domain in LEGAL_DOMAINS:
        if domain["id"] == domain_id:
            return domain
    raise ValueError("Domaine juridique inconnu")


def _legal_text(value, *, required=False, limit=500):
    value = str(value or "").strip()
    if (required and not value) or len(value) > limit:
        raise ValueError("Texte obligatoire ou trop long")
    return value


def _legal_row(conn, table, project_id, row_id):
    row = conn.execute(f"SELECT * FROM {table} WHERE id=? AND project_id=?", (row_id, project_id)).fetchone()
    if row is None:
        raise ValueError("Élément introuvable dans ce projet")
    return dict(row)


def _legal_date(value):
    value = _legal_text(value, required=True, limit=10)
    date.fromisoformat(value)
    return value


def _legal_integer(value, low=0, high=1_000_000_000):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Montant ou durée invalide")
    return value


def _legal_round(value):
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def legal_snapshot(conn, project_id):
    workspace = conn.execute("SELECT domain, matter_types FROM legal_workspaces WHERE project_id=?", (project_id,)).fetchone()
    result = {"project_id": project_id, "domain": workspace["domain"] if workspace else None,
              "matter_types": json.loads(workspace["matter_types"]) if workspace else [],
              "domains": list(LEGAL_DOMAINS)}
    for key in ("clients", "matters", "acts", "fees", "documents", "payments"):
        rows = conn.execute(f"SELECT * FROM legal_{key} WHERE project_id=? ORDER BY rowid", (project_id,)).fetchall()
        result[key] = [{k: row[k] for k in row.keys() if k != "project_id"} for row in rows]
    for document in result["documents"]:
        document["snapshot"] = json.loads(document["snapshot"])
        document["paid_cents"] = sum(p["amount_cents"] for p in result["payments"] if p["document_id"] == document["id"])
        document["balance_cents"] = document["total_cents"] - document["paid_cents"]
    return result


def legal_mutate(conn, project_id, action, params):
    """All validation and writes share one lock; replayed monetary operations do not duplicate."""
    payload = json.dumps({"action": action, **{k: v for k, v in params.items() if k not in ("profile", "project_id")}}, sort_keys=True, ensure_ascii=False)
    request_id = params.get("request_id")
    with write_txn(conn):
        if action in ("fee.add", "document.create", "payment.add"):
            request_id = _legal_text(request_id, required=True, limit=100)
            existing = conn.execute("SELECT payload FROM legal_requests WHERE project_id=? AND request_id=?", (project_id, request_id)).fetchone()
            if existing:
                if existing["payload"] != payload:
                    raise ValueError("Cette opération existe déjà avec un contenu différent")
                return legal_snapshot(conn, project_id)
        _legal_apply(conn, project_id, action, params)
        if request_id:
            conn.execute("INSERT INTO legal_requests VALUES (?,?,?)", (project_id, request_id, payload))
        return legal_snapshot(conn, project_id)


def _legal_apply(conn, pid, action, p):
    if action == "workspace.set":
        domain = legal_domain(p.get("domain"))
        types = p.get("matter_types") or domain["matter_types"]
        types = list(dict.fromkeys(_legal_text(t, required=True, limit=100) for t in types))
        if not 1 <= len(types) <= 100:
            raise ValueError("Choisir entre 1 et 100 types de dossiers")
        used = {r[0] for r in conn.execute("SELECT matter_type FROM legal_matters WHERE project_id=?", (pid,))}
        if not used.issubset(types):
            raise ValueError("Conserver les types des dossiers existants")
        conn.execute("INSERT INTO legal_workspaces VALUES (?,?,?) ON CONFLICT(project_id) DO UPDATE SET domain=excluded.domain, matter_types=excluded.matter_types", (pid, domain["id"], json.dumps(types, ensure_ascii=False)))
        return
    if action in ("client.save", "matter.save", "act.save"):
        row_id = p.get("id") or secrets.token_hex(16)
        table = {"client.save": "legal_clients", "matter.save": "legal_matters", "act.save": "legal_acts"}[action]
        if p.get("id"):
            _legal_row(conn, table, pid, row_id)
        if action == "client.save":
            values = {"name": _legal_text(p.get("name"), required=True), "email": _legal_text(p.get("email")), "address": _legal_text(p.get("address"), limit=2000)}
        elif action == "act.save":
            values = {"title": _legal_text(p.get("title"), required=True), "act_type": _legal_text(p.get("act_type"), required=True), "body": _legal_text(p.get("body"), limit=200_000)}
        else:
            _legal_row(conn, "legal_clients", pid, p.get("client_id"))
            workspace = legal_snapshot(conn, pid)
            if p.get("matter_type") not in workspace["matter_types"]:
                raise ValueError("Configurer le domaine et choisir un type de dossier")
            if p.get("status", "open") not in ("open", "closed"):
                raise ValueError("Statut de dossier invalide")
            values = {"client_id": p["client_id"], "title": _legal_text(p.get("title"), required=True), "matter_type": p["matter_type"], "reference": _legal_text(p.get("reference")), "status": p.get("status", "open")}
        if p.get("id"):
            columns = ",".join(f"{key}=?" for key in values)
            conn.execute(f"UPDATE {table} SET {columns} WHERE id=? AND project_id=?", (*values.values(), row_id, pid))
        else:
            columns = ",".join(values)
            marks = ",".join("?" for _ in values)
            conn.execute(f"INSERT INTO {table} (id,project_id,{columns}) VALUES (?, ?,{marks})", (row_id, pid, *values.values()))
        return
    if action == "fee.add":
        _legal_row(conn, "legal_matters", pid, p.get("matter_id"))
        kind = p.get("kind")
        if kind not in ("fixed", "time"):
            raise ValueError("Type d'honoraires invalide")
        minutes = _legal_integer(p.get("minutes", 0), high=1_000_000)
        rate = _legal_integer(p.get("rate_cents", 0))
        net = _legal_round(Decimal(minutes) * rate / 60) if kind == "time" else _legal_integer(p.get("amount_cents", 0))
        if net <= 0 or (kind == "time" and (minutes == 0 or rate == 0)):
            raise ValueError("Honoraires strictement positifs requis")
        _legal_integer(net)
        tax_bps = _legal_integer(p.get("tax_bps", 0), high=10000)
        tax = _legal_round(Decimal(net) * tax_bps / 10000)
        conn.execute("INSERT INTO legal_fees VALUES (?,?,?,?,?,?,?,?,?,?,NULL)", (secrets.token_hex(16), pid, p["matter_id"], _legal_text(p.get("description"), required=True), kind, minutes, rate, net, tax_bps, tax))
        return
    if action == "document.create":
        matter = _legal_row(conn, "legal_matters", pid, p.get("matter_id"))
        client = _legal_row(conn, "legal_clients", pid, matter["client_id"])
        kind = p.get("kind")
        if kind not in ("quote", "invoice"):
            raise ValueError("Type de document invalide")
        ids = p.get("fee_ids") or []
        if not ids or len(ids) != len(set(ids)) or len(ids) > 500:
            raise ValueError("Sélectionner entre 1 et 500 honoraires distincts")
        fees = [_legal_row(conn, "legal_fees", pid, fee_id) for fee_id in ids]
        if any(f["matter_id"] != matter["id"] or (kind == "invoice" and f["invoice_id"]) for f in fees):
            raise ValueError("Honoraires d'un autre dossier ou déjà facturés")
        due_on = _legal_date(p.get("due_on"))
        today = date.today().isoformat()
        if due_on < today:
            raise ValueError("L'échéance doit être aujourd'hui ou ultérieure")
        doc_id = secrets.token_hex(16)
        count = conn.execute("SELECT COUNT(*) FROM legal_documents WHERE project_id=?", (pid,)).fetchone()[0] + 1
        ref = f"{'DEV' if kind == 'quote' else 'FAC'}-BROUILLON-{count:05d}"
        net, tax = sum(f["net_cents"] for f in fees), sum(f["tax_cents"] for f in fees)
        snapshot = {"client": {k: client[k] for k in ("name", "email", "address")}, "matter": {k: matter[k] for k in ("title", "reference")}, "lines": [{k: f[k] for k in ("description", "net_cents", "tax_bps", "tax_cents")} for f in fees]}
        conn.execute("INSERT INTO legal_documents VALUES (?,?,?,?,?,?,?,?,?,?,?)", (doc_id, pid, matter["id"], kind, ref, today, due_on, json.dumps(snapshot, ensure_ascii=False), net, tax, net + tax))
        if kind == "invoice":
            conn.executemany("UPDATE legal_fees SET invoice_id=? WHERE id=? AND project_id=?", [(doc_id, f["id"], pid) for f in fees])
        return
    if action == "payment.add":
        doc = _legal_row(conn, "legal_documents", pid, p.get("document_id"))
        if doc["kind"] != "invoice":
            raise ValueError("Enregistrer un règlement sur une facture de travail")
        amount = _legal_integer(p.get("amount_cents"), low=1)
        paid = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM legal_payments WHERE document_id=?", (doc["id"],)).fetchone()[0]
        if amount > doc["total_cents"] - paid:
            raise ValueError("Le règlement dépasse le solde")
        paid_on = _legal_date(p.get("paid_on"))
        if paid_on > date.today().isoformat():
            raise ValueError("Un règlement reçu ne peut pas être daté dans le futur")
        conn.execute("INSERT INTO legal_payments VALUES (?,?,?,?,?,?)", (secrets.token_hex(16), pid, doc["id"], amount, paid_on, _legal_text(p.get("reference"), required=True)))
        return
    raise ValueError("Opération juridique inconnue")

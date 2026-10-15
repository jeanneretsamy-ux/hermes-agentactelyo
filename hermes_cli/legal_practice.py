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
    {"id": "penal", "label": "Droit Pénal et Procédure", "matter_types": ["Défense pénale", "Victime", "Instruction", "Audience", "Exécution des peines", "Garde à vue", "Comparution immédiate", "Appel pénal"], "act_types": ["Plainte", "Constitution de partie civile", "Demande d'actes", "Conclusions pénales", "Mémoire d'appel", "Demande de mise en liberté"]},
    {"id": "contentieux-judiciaire", "label": "Contentieux Judiciaire", "matter_types": ["Procédure civile", "Référé", "Appel", "Exécution d'une décision", "Expertise judiciaire"], "act_types": ["Assignation", "Conclusions", "Requête", "Conclusions d'appel", "Incident de procédure"]},
    {"id": "commercial", "label": "Droit des Affaires", "matter_types": ["Contrats commerciaux", "Recouvrement", "Litige commercial", "Entreprise en difficulté", "Concurrence", "Distribution"], "act_types": ["Contrat commercial", "Conditions générales", "Mise en demeure", "Assignation", "Protocole transactionnel"]},
    {"id": "societes", "label": "Droit des Sociétés", "matter_types": ["Constitution", "Vie sociale", "Cession de titres", "Restructuration", "Dissolution", "Conflit entre associés", "Opération sur capital"], "act_types": ["Statuts", "Procès-verbal d'assemblée", "Pacte d'associés", "Cession de titres", "Rapport de gestion"]},
    {"id": "social", "label": "Droit Social / Travail", "matter_types": ["Embauche", "Relations collectives", "Rupture du contrat", "Contentieux prud'homal", "Accident du travail", "Discrimination"], "act_types": ["Contrat de travail", "Avenant", "Accord collectif", "Conclusions prud'homales", "Lettre de licenciement"]},
    {"id": "fiscal", "label": "Droit Fiscal", "matter_types": ["Conseil fiscal", "Contrôle fiscal", "Réclamation", "Contentieux fiscal", "Fiscalité des sociétés", "Fiscalité patrimoniale"], "act_types": ["Note fiscale", "Réponse à une proposition de rectification", "Réclamation contentieuse", "Recours fiscal"]},
    {"id": "notarie", "label": "Droit Notarié", "matter_types": ["Vente immobilière", "Succession", "Donation", "Régime matrimonial", "Acte authentique"], "act_types": ["Promesse de vente", "Projet d'acte", "Convention de partage", "Mandat"]},
    {"id": "immobilier", "label": "Baux & Contrats", "matter_types": ["Bail", "Copropriété", "Construction", "Vente immobilière", "Bail commercial", "Rédaction contractuelle", "Résiliation de contrat"], "act_types": ["Bail", "Mise en demeure", "Conclusions", "Protocole transactionnel", "Avenant au bail", "Contrat de prestation"]},
    {"id": "sport", "label": "Droit du Sport", "matter_types": ["Contrat de sportif", "Transfert", "Discipline sportive", "Droit à l'image", "Litige fédéral"], "act_types": ["Contrat de joueur", "Convention de transfert", "Recours disciplinaire", "Licence d'exploitation d'image"]},
    {"id": "agricole", "label": "Droit Agricole", "matter_types": ["Bail rural", "Exploitation agricole", "Transmission d'exploitation", "Coopérative agricole", "Aides agricoles"], "act_types": ["Bail rural", "Cession d'exploitation", "Statuts de société agricole", "Convention de mise à disposition"]},
    {"id": "transport", "label": "Droit du Transport", "matter_types": ["Transport de marchandises", "Transport de voyageurs", "Responsabilité du transporteur", "Litige logistique", "Assurance transport"], "act_types": ["Contrat de transport", "Réclamation transport", "Mise en demeure", "Protocole d'indemnisation"]},
    {"id": "douane", "label": "Droit de Douane", "matter_types": ["Déclaration douanière", "Contentieux douanier", "Contrôle douanier", "Classement tarifaire", "Origine des marchandises"], "act_types": ["Recours douanier", "Réponse à notification", "Demande de classement tarifaire", "Mémoire douanier"]},
    {"id": "medical", "label": "Droit Médical", "matter_types": ["Responsabilité médicale", "Accident médical", "Droit des patients", "Exercice professionnel", "Établissement de santé"], "act_types": ["Réclamation médicale", "Demande de dossier médical", "Assignation en responsabilité", "Protocole d'indemnisation"]},
    {"id": "recouvrement", "label": "Recouvrement", "matter_types": ["Recouvrement amiable", "Injonction de payer", "Exécution forcée", "Créance contestée", "Procédure collective"], "act_types": ["Mise en demeure de payer", "Requête en injonction de payer", "Commandement de payer", "Déclaration de créance"]},
    {"id": "patrimonial-famille", "label": "Droit Patrimonial et Famille", "matter_types": ["Divorce", "Succession", "Liquidation de régime matrimonial", "Donation", "Partage familial", "Protection patrimoniale"], "act_types": ["Convention de divorce", "Convention de partage", "Requête familiale", "Mandat de protection future"]},
    {"id": "personnes-protegees", "label": "Droit des Personnes Protégées", "matter_types": ["Tutelle", "Curatelle", "Habilitation familiale", "Mandat de protection future", "Mesure de sauvegarde"], "act_types": ["Requête en ouverture de mesure", "Requête en renouvellement", "Inventaire patrimonial", "Compte de gestion"]},
    {"id": "civil", "label": "Droit Civil", "matter_types": ["Responsabilité", "Contrats", "Divorce", "Succession", "Responsabilité délictuelle", "Droit des biens", "Obligations"], "act_types": ["Assignation", "Conclusions", "Protocole d'accord", "Convention", "Mise en demeure"]},
    {"id": "ntic-propriete-intellectuelle", "label": "Droit NTIC & Propriété Intellectuelle", "matter_types": ["Droit d'auteur", "Marque", "Données personnelles", "Contrat informatique", "Contentieux numérique", "Nom de domaine"], "act_types": ["Contrat de licence", "Mise en demeure contrefaçon", "Politique de confidentialité", "Contrat informatique", "Opposition à marque"]},
    {"id": "esport", "label": "Droit de l'E-Sport", "matter_types": ["Contrat de joueur e-sport", "Transfert e-sport", "Équipe et compétition", "Sponsoring", "Droit à l'image numérique"], "act_types": ["Contrat de joueur e-sport", "Contrat de sponsoring", "Convention de transfert", "Licence de diffusion"]},
    {"id": "aerien", "label": "Droit Aérien", "matter_types": ["Transport aérien", "Responsabilité aérienne", "Droit des passagers", "Exploitation aéronautique", "Litige aéroportuaire"], "act_types": ["Réclamation passager", "Mise en demeure transporteur", "Contrat d'affrètement", "Recours indemnitaire"]},
    {"id": "administratif", "label": "Droit administratif", "matter_types": ["Recours", "Marchés publics", "Urbanisme", "Responsabilité administrative"], "act_types": ["Recours gracieux", "Requête", "Mémoire", "Référé"]},
)

_LEGAL_SCHEMA = """
CREATE TABLE IF NOT EXISTS legal_workspaces (
 project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
 domain TEXT NOT NULL, matter_types TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS legal_clients (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 name TEXT NOT NULL, email TEXT NOT NULL, address TEXT NOT NULL,
 customer_type TEXT NOT NULL DEFAULT 'individual', siren TEXT NOT NULL DEFAULT ''
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
 invoice_id TEXT, responsible_user TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS legal_firm_settings (
 id INTEGER PRIMARY KEY CHECK(id=1), jurisdiction TEXT NOT NULL DEFAULT 'FR',
 legal_name TEXT NOT NULL DEFAULT '', address TEXT NOT NULL DEFAULT '', siren TEXT NOT NULL DEFAULT '',
 vat_number TEXT NOT NULL DEFAULT '', vat_regime TEXT NOT NULL DEFAULT 'standard',
 bar_name TEXT NOT NULL DEFAULT '', payment_delay_days INTEGER NOT NULL DEFAULT 30,
 late_penalty_rate TEXT NOT NULL DEFAULT '3 fois le taux d’intérêt légal'
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
    columns = {row[1] for row in conn.execute("PRAGMA table_info(legal_fees)")}
    if "responsible_user" not in columns:
        conn.execute("ALTER TABLE legal_fees ADD COLUMN responsible_user TEXT NOT NULL DEFAULT ''")
    client_columns = {row[1] for row in conn.execute("PRAGMA table_info(legal_clients)")}
    if "customer_type" not in client_columns:
        conn.execute("ALTER TABLE legal_clients ADD COLUMN customer_type TEXT NOT NULL DEFAULT 'individual'")
    if "siren" not in client_columns:
        conn.execute("ALTER TABLE legal_clients ADD COLUMN siren TEXT NOT NULL DEFAULT ''")


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
    settings = conn.execute("SELECT * FROM legal_firm_settings WHERE id=1").fetchone()
    result["firm_settings"] = {k: settings[k] for k in settings.keys() if k != "id"} if settings else {
        "jurisdiction": "FR", "legal_name": "", "address": "", "siren": "", "vat_number": "",
        "vat_regime": "standard", "bar_name": "", "payment_delay_days": 30,
        "late_penalty_rate": "3 fois le taux d’intérêt légal",
    }
    # The profile database is the cabinet boundary. These totals consolidate its projects,
    # while the detail lists above remain scoped to the selected project.
    result["firm_totals"] = _firm_totals(conn)
    return result


def render_legal_document(document):
    """Render a saved quote/invoice snapshot as a readable, source-faithful Markdown draft."""
    snapshot = document["snapshot"]
    client, matter = snapshot["client"], snapshot["matter"]

    def money(cents):
        value = f"{cents / 100:,.2f}"
        return value.replace(",", "\u202f").replace(".", ",") + " €"

    def date_fr(value):
        return date.fromisoformat(value).strftime("%d/%m/%Y")

    def cell(value):
        return str(value or "").replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()

    is_invoice = document["kind"] == "invoice"
    title = "Facture" if is_invoice else "Devis"
    lines = [
        f"# {title} — BROUILLON À RELIRE",
        "",
        f"**Référence provisoire :** {document['reference']}  ",
        f"**Date du document :** {date_fr(document['created_on'])}  ",
        f"**Échéance indiquée :** {date_fr(document['due_on'])}",
    ]
    issuer = snapshot.get("issuer")
    if issuer:
        lines.extend(["", "## Cabinet émetteur", f"**{cell(issuer['legal_name'])}**", cell(issuer["address"]),
                      f"SIREN : {cell(issuer['siren'])}"])
        if issuer.get("vat_number"):
            lines.append(f"TVA intracommunautaire : {cell(issuer['vat_number'])}")
        if issuer.get("bar_name"):
            lines.append(f"Barreau : {cell(issuer['bar_name'])}")
    lines.extend(["", "## Client", f"**{cell(client['name'])}**"])
    if client.get("address"):
        lines.append(cell(client["address"]))
    if client.get("email"):
        lines.append(f"Courriel : {cell(client['email'])}")
    if client.get("customer_type") == "professional" and client.get("siren"):
        lines.append(f"SIREN client : {cell(client['siren'])}")
    lines.extend(["", "## Dossier", f"{cell(matter['title'])}" + (f" — réf. {cell(matter['reference'])}" if matter.get("reference") else ""),
                  "", "## Détail des prestations", "",
                  "| Prestation | Montant HT | Taux TVA | TVA | Montant TTC |",
                  "|---|---:|---:|---:|---:|"])
    for item in snapshot["lines"]:
        lines.append(
            f"| {cell(item['description'])} | {money(item['net_cents'])} | "
            f"{item['tax_bps'] / 100:g} % | {money(item['tax_cents'])} | "
            f"{money(item['net_cents'] + item['tax_cents'])} |"
        )
    lines.extend(["", f"**Total HT : {money(document['net_cents'])}**  ",
                  f"**TVA : {money(document['tax_cents'])}**  ",
                  f"# Total TTC : {money(document['total_cents'])}"])
    if snapshot.get("vat_notice"):
        lines.extend(["", cell(snapshot["vat_notice"])])
    terms = snapshot.get("payment_terms")
    if terms:
        lines.extend(["", "## Règlement", f"Échéance : {date_fr(terms['due_on'])} ({terms['delay_days']} jours).",
                      f"Pénalités de retard prévues au paramétrage : {cell(terms['late_penalty_rate'])}."])
        if client.get("customer_type") == "professional":
            lines.append(f"Indemnité forfaitaire pour frais de recouvrement : {money(terms['recovery_indemnity_cents'])}.")
    paid = document.get("paid_cents", 0)
    if is_invoice:
        lines.extend(["", "## Suivi interne", f"Règlements enregistrés : {money(paid)}  ",
                      f"Solde calculé : {money(document['total_cents'] - paid)}"])
    lines.extend(["", "---", "**BROUILLON INTERNE — NON ÉMIS.** Vérifier les mentions, les taux, les dates, les conditions convenues et les pièces sources avant toute émission au client."])
    return "\n".join(lines)


def _firm_totals(conn):
    by_project = conn.execute("""SELECT p.id AS project_id,p.name,
      COALESCE(SUM(f.net_cents),0) AS fees_cents,COUNT(f.id) AS fee_count
      FROM projects p LEFT JOIN legal_fees f ON f.project_id=p.id
      GROUP BY p.id,p.name ORDER BY p.name""").fetchall()
    by_user = conn.execute("""SELECT COALESCE(NULLIF(f.responsible_user,''),'Non attribué') AS user,
      COALESCE(SUM(f.net_cents),0) AS fees_cents,COUNT(f.id) AS fee_count
      FROM legal_fees f GROUP BY COALESCE(NULLIF(f.responsible_user,''),'Non attribué')
      ORDER BY user""").fetchall()
    by_matter = conn.execute("""SELECT m.project_id,p.name AS project,m.id AS matter_id,m.title,
      COALESCE(SUM(f.net_cents),0) AS fees_cents,COUNT(f.id) AS fee_count
      FROM legal_matters m JOIN projects p ON p.id=m.project_id
      LEFT JOIN legal_fees f ON f.matter_id=m.id AND f.project_id=m.project_id
      GROUP BY m.project_id,p.name,m.id,m.title ORDER BY p.name,m.title""").fetchall()
    totals = conn.execute("""SELECT COALESCE(SUM(net_cents),0) AS fees_cents,
      COUNT(*) AS fee_count FROM legal_fees""").fetchone()
    docs = conn.execute("""SELECT COALESCE(SUM(d.total_cents),0) AS invoiced_cents,
      COALESCE((SELECT SUM(amount_cents) FROM legal_payments),0) AS paid_cents
      FROM legal_documents d WHERE d.kind='invoice'""").fetchone()
    return {"fees_cents": totals["fees_cents"], "fee_count": totals["fee_count"],
            "invoiced_cents": docs["invoiced_cents"], "paid_cents": docs["paid_cents"],
            "balance_cents": docs["invoiced_cents"] - docs["paid_cents"],
            "by_project": [dict(row) for row in by_project], "by_user": [dict(row) for row in by_user],
            "by_matter": [dict(row) for row in by_matter]}


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
    if action == "firm.settings.set":
        if p.get("jurisdiction") != "FR":
            raise ValueError("La juridiction France est disponible. Les autres juridictions ne sont pas encore prises en charge.")
        name = _legal_text(p.get("legal_name"), required=True, limit=200)
        address = _legal_text(p.get("address"), required=True, limit=2000)
        siren = "".join(ch for ch in str(p.get("siren", "")) if ch.isdigit())
        if len(siren) != 9:
            raise ValueError("Le SIREN du cabinet doit comporter 9 chiffres.")
        regime = p.get("vat_regime")
        if regime not in ("standard", "franchise"):
            raise ValueError("Régime de TVA France invalide")
        delay = _legal_integer(p.get("payment_delay_days", 30), low=1, high=60)
        conn.execute("""INSERT INTO legal_firm_settings
          (id,jurisdiction,legal_name,address,siren,vat_number,vat_regime,bar_name,payment_delay_days,late_penalty_rate)
          VALUES (1,'FR',?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
          jurisdiction='FR',legal_name=excluded.legal_name,address=excluded.address,siren=excluded.siren,
          vat_number=excluded.vat_number,vat_regime=excluded.vat_regime,bar_name=excluded.bar_name,
          payment_delay_days=excluded.payment_delay_days,late_penalty_rate=excluded.late_penalty_rate""",
          (name,address,siren,_legal_text(p.get("vat_number"),limit=40),regime,
           _legal_text(p.get("bar_name"),limit=200),delay,
           _legal_text(p.get("late_penalty_rate"),required=True,limit=200)))
        return
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
            customer_type = p.get("customer_type", "individual")
            if customer_type not in ("individual", "professional"):
                raise ValueError("Type de client invalide")
            siren = "".join(ch for ch in str(p.get("siren", "")) if ch.isdigit())
            if siren and len(siren) != 9:
                raise ValueError("Le SIREN du client doit comporter 9 chiffres.")
            values = {"name": _legal_text(p.get("name"), required=True), "email": _legal_text(p.get("email")), "address": _legal_text(p.get("address"), limit=2000), "customer_type": customer_type, "siren": siren}
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
        conn.execute("INSERT INTO legal_fees (id,project_id,matter_id,description,kind,minutes,rate_cents,net_cents,tax_bps,tax_cents,invoice_id,responsible_user) VALUES (?,?,?,?,?,?,?,?,?,?,NULL,?)", (secrets.token_hex(16), pid, p["matter_id"], _legal_text(p.get("description"), required=True), kind, minutes, rate, net, tax_bps, tax, _legal_text(p.get("responsible_user"), limit=200)))
        return
    if action == "document.create":
        matter = _legal_row(conn, "legal_matters", pid, p.get("matter_id"))
        client = _legal_row(conn, "legal_clients", pid, matter["client_id"])
        kind = p.get("kind")
        if kind not in ("quote", "invoice"):
            raise ValueError("Type de document invalide")
        settings = conn.execute("SELECT * FROM legal_firm_settings WHERE id=1").fetchone()
        if kind == "invoice" and (not settings or not settings["legal_name"] or not settings["address"] or not settings["siren"] or (settings["vat_regime"] == "standard" and not settings["vat_number"])):
            raise ValueError("Renseignez l’identité, l’adresse, le SIREN et, si le cabinet est assujetti, le numéro de TVA dans les paramètres de facturation.")
        ids = p.get("fee_ids") or []
        if not ids or len(ids) != len(set(ids)) or len(ids) > 500:
            raise ValueError("Sélectionner entre 1 et 500 honoraires distincts")
        fees = [_legal_row(conn, "legal_fees", pid, fee_id) for fee_id in ids]
        if kind == "invoice" and (not client["address"].strip() or (client["customer_type"] == "professional" and len(client["siren"]) != 9)):
            raise ValueError("Complétez l’adresse du client et, pour un client professionnel, son SIREN avant la facture.")
        if any(f["matter_id"] != matter["id"] or (kind == "invoice" and f["invoice_id"]) for f in fees):
            raise ValueError("Honoraires d'un autre dossier ou déjà facturés")
        if kind == "invoice" and settings["vat_regime"] == "franchise" and any(f["tax_bps"] for f in fees):
            raise ValueError("Le régime de franchise en base ne peut pas facturer de TVA. Corrigez les honoraires avant de créer la facture.")
        due_on = _legal_date(p.get("due_on"))
        today = date.today().isoformat()
        if due_on < today:
            raise ValueError("L'échéance doit être aujourd'hui ou ultérieure")
        doc_id = secrets.token_hex(16)
        count = conn.execute("SELECT COUNT(*) FROM legal_documents WHERE kind=?", (kind,)).fetchone()[0] + 1
        ref = f"{'DEV' if kind == 'quote' else 'FAC'}-BROUILLON-{date.today().year}-{count:05d}"
        net, tax = sum(f["net_cents"] for f in fees), sum(f["tax_cents"] for f in fees)
        snapshot = {"client": {k: client[k] for k in ("name", "email", "address", "customer_type", "siren")}, "matter": {k: matter[k] for k in ("title", "reference")}, "lines": [{k: f[k] for k in ("description", "net_cents", "tax_bps", "tax_cents")} for f in fees]}
        if kind == "invoice":
            snapshot["jurisdiction"] = "FR"
            snapshot["issuer"] = {k: settings[k] for k in ("legal_name", "address", "siren", "vat_number", "vat_regime", "bar_name")}
            snapshot["payment_terms"] = {"due_on": due_on, "delay_days": settings["payment_delay_days"],
                "late_penalty_rate": settings["late_penalty_rate"], "recovery_indemnity_cents": 4000}
            snapshot["vat_notice"] = "TVA non applicable, article 293 B du CGI" if settings["vat_regime"] == "franchise" else ""
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


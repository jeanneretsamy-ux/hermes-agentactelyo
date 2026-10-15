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

LEGAL_PRACTICE_DOCUMENT_TEMPLATES = (
    ("invoice_appendix", "Annexe facture"), ("invoice_cancellation", "Annulation de facture"),
    ("credit_note", "Avoir"), ("document_communication", "Bordereau de communication de pièces"),
    ("carpa_movements", "Bordereau de mouvement CARPA"), ("case_list", "Bordereau liste / cote dossier"),
    ("remittance_cheque", "Bordereau de remise par chèque"), ("remittance_invoice", "Bordereau de remise par facture"),
    ("end_of_mission", "Compte rendu de fin de mission"), ("support_letter_2777", "Courrier d'accompagnement 2777"),
    ("fixed_withdrawal_exemption", "Dispense de prélèvement forfaitaire"), ("payments_list", "Édition des règlements"),
    ("labels", "Étiquettes"), ("subscription_invoice", "Facture d'abonnement"),
    ("detailed_invoice", "Facture détaillée"), ("detailed_invoice_matter", "Facture détaillée par dossier"),
    ("expense_invoice", "Facture état de frais"), ("free_invoice", "Facture libre"),
    ("summary_invoice", "Facture résumée"), ("fax", "Fax"),
    ("attendance_landscape", "Feuille de présence paysage"), ("attendance_portrait", "Feuille de présence portrait"),
    ("expense_statement", "Impression état de frais"), ("carpa_letter", "Lettre CARPA"),
    ("mailing", "Mailing"), ("reimbursement_receipt", "Reçu remboursement"),
    ("quick_letter", "Rédaction rapide d'un courrier"), ("registered_letter_ack", "Recommandé avec accusé de réception"),
    ("registered_letter", "Recommandé sans accusé de réception"),
    ("reminder_1", "Relance 1"), ("reminder_2", "Relance 2"), ("reminder_3", "Relance 3"),
    ("reminder_4", "Relance 4"), ("reminder_5", "Relance 5"),
    ("email_reminder", "Relance par mail"), ("payment_delay_table", "Tableau de délai de paiement"),
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
 matter_type TEXT NOT NULL, reference TEXT NOT NULL, status TEXT NOT NULL,
 company_profile TEXT NOT NULL DEFAULT '{}', matter_profile TEXT NOT NULL DEFAULT '{}'
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
 invoice_id TEXT, responsible_user TEXT NOT NULL DEFAULT '', activity_date TEXT NOT NULL DEFAULT '',
 billing_code TEXT NOT NULL DEFAULT '', activity_type TEXT NOT NULL DEFAULT '', billable INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS legal_fee_codes (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 code TEXT NOT NULL, label TEXT NOT NULL, hourly_rate_cents INTEGER NOT NULL DEFAULT 0,
 fixed_amount_cents INTEGER NOT NULL DEFAULT 0, tax_bps INTEGER NOT NULL DEFAULT 0,
 UNIQUE(project_id,code)
);
CREATE TABLE IF NOT EXISTS legal_subscriptions (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 matter_id TEXT NOT NULL REFERENCES legal_matters(id), label TEXT NOT NULL,
 amount_cents INTEGER NOT NULL, tax_bps INTEGER NOT NULL DEFAULT 0,
 cadence TEXT NOT NULL, starts_on TEXT NOT NULL, ends_on TEXT NOT NULL DEFAULT '',
 next_invoice_on TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
 UNIQUE(project_id,matter_id,label)
);
CREATE TABLE IF NOT EXISTS legal_practice_documents (
 id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
 matter_id TEXT NOT NULL REFERENCES legal_matters(id), template_id TEXT NOT NULL,
 title TEXT NOT NULL, body TEXT NOT NULL, fee_ids TEXT NOT NULL DEFAULT '[]', created_on TEXT NOT NULL
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
 total_cents INTEGER NOT NULL, purpose TEXT NOT NULL DEFAULT 'standard',
 related_document_id TEXT REFERENCES legal_documents(id)
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
    document_columns = {row[1] for row in conn.execute("PRAGMA table_info(legal_documents)")}
    if "purpose" not in document_columns:
        conn.execute("ALTER TABLE legal_documents ADD COLUMN purpose TEXT NOT NULL DEFAULT 'standard'")
    if "related_document_id" not in document_columns:
        conn.execute("ALTER TABLE legal_documents ADD COLUMN related_document_id TEXT REFERENCES legal_documents(id)")
    fee_columns = {row[1] for row in conn.execute("PRAGMA table_info(legal_fees)")}
    matter_columns = {row[1] for row in conn.execute("PRAGMA table_info(legal_matters)")}
    if "company_profile" not in matter_columns:
        conn.execute("ALTER TABLE legal_matters ADD COLUMN company_profile TEXT NOT NULL DEFAULT '{}' ")
    if "matter_profile" not in matter_columns:
        conn.execute("ALTER TABLE legal_matters ADD COLUMN matter_profile TEXT NOT NULL DEFAULT '{}' ")
    conn.execute("UPDATE legal_matters SET matter_profile=company_profile WHERE matter_profile='{}' AND company_profile!='{}'")
    for name, definition in (("activity_date", "TEXT NOT NULL DEFAULT ''"), ("billing_code", "TEXT NOT NULL DEFAULT ''"),
                             ("activity_type", "TEXT NOT NULL DEFAULT ''"), ("billable", "INTEGER NOT NULL DEFAULT 1")):
        if name not in fee_columns:
            conn.execute(f"ALTER TABLE legal_fees ADD COLUMN {name} {definition}")


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


SOCIETY_PROFILE_LABELS = {
    "matter_organization": ("Organisation du dossier", {"summary": "Résumé", "cote": "Cote", "secondary_sections": "Rubriques secondaires", "formulas": "Formules", "documents": "Documents liés", "models": "Modèles", "headers": "En-têtes"}),
    "company_details": ("Détail société", {"legal_form": "Forme juridique", "registered_name": "Dénomination sociale", "trade_name": "Nom commercial", "registration_number": "RCS / registre et ville", "siren": "SIREN", "siret": "SIRET", "vat_number": "N° TVA intracommunautaire", "registered_office": "Siège social", "activity": "Activité / objet social", "financial_year": "Exercice social", "duration": "Durée de la société"}),
    "capital_rights": ("Capital et droits sociaux", {"capital": "Capital social", "shares": "Parts / actions et valeur nominale", "voting_rights": "Droits de vote", "special_rights": "Droits particuliers", "capital_changes": "Variations de capital"}),
    "history": ("Historique", {"events": "Événements et modifications"}),
    "dividends": ("Dividendes", {"decisions": "Décisions et distributions"}),
    "current_accounts": ("Intérêts de compte courant", {"accounts": "Associé, solde, taux et périodes"}),
    "share_transfers": ("Cessions de parts", {"transfers": "Cédant, cessionnaire, titres, prix et dates"}),
    "remuneration": ("Rémunérations", {"remuneration": "Bénéficiaire, fonction, montants et décisions"}),
    "associates": ("Associés", {"members": "Identité, coordonnées, titres et droits de chaque associé"}),
    "management": ("Administration", {"president": "Président", "vice_president": "Vice-président", "general_managers": "Directeurs généraux", "deputy_general_managers": "Directeurs généraux délégués", "manager_details": "Infos générales DG / DGD"}),
    "agreements": ("Conventions", {"agreements": "Conventions réglementées et autres conventions"}),
    "delegations": ("Délégation de pouvoirs", {"delegations": "Délégant, délégataire, pouvoirs et durée"}),
    "meetings": ("Assemblées du dossier", {"meetings": "Date, type, convocations, décisions et procès-verbaux"}),
    "control_bodies": ("Organes de contrôle", {"statutory_auditors": "Commissaires aux comptes titulaires", "alternate_auditors": "Commissaires aux comptes suppléants", "contribution_auditors": "Commissaires aux apports", "accountants": "Experts-comptables", "supervisory_board_president": "Président du conseil de surveillance", "supervisory_board_vice_president": "Vice-président du conseil de surveillance", "supervisory_board_members": "Membres du conseil de surveillance", "supervisory_board_details": "Informations sur le conseil de surveillance"}),
    "assets": ("Patrimoine", {"goods": "Biens", "establishments": "Établissements secondaires", "subsidiaries": "Filiales", "contracts": "Contrats en cours", "leases": "Baux", "patents": "Brevets", "trademarks": "Marques", "designs": "Dessins et modèles", "works_council": "Membres du CSE"}),
    "billable_clients": ("Clients facturés / Tiers", {"third_parties": "Clients facturés et tiers"}),
    "tax": ("Fiscal", {"tax_regime": "Régime fiscal", "tax_ids": "Identifiants fiscaux", "tax_calendar": "Échéances et obligations fiscales", "tax_notes": "Autres informations fiscales"}),
}


COMMON_MATTER_PROFILE = {
    "matter_organization": ("Menu du dossier", {"summary": "Résumé", "cote": "Cote", "secondary_sections": "Rubriques secondaires", "formulas": "Formules", "documents": "Documents", "models": "Modèles", "headers": "En-têtes", "correspondence": "Courriers", "expenses": "Frais", "misc_documents": "Documents divers"}),
    "evidence_register": ("Bordereau / Pièces", {"piece_list": "Liste des pièces et numéros", "received_pieces": "Pièces reçues", "missing_pieces": "Pièces à demander", "piece_notes": "Notes sur les pièces"}),
    "document_generator": ("Générateur", {"document_to_create": "Document à générer", "drafting_instructions": "Consignes de rédaction", "reference_examples": "Exemples de référence", "sections_to_rework": "Parties à modifier ou compléter"}),
    "billable_clients": ("Clients facturés / Tiers", {"third_parties": "Clients facturés / Tiers"}),
}


DOMAIN_MATTER_PROFILE = {
    "penal": {
        "people": ("Personnes", {"client": "Client / mis en cause / victime", "opposing_parties": "Parties adverses", "witnesses": "Témoins", "lawyers": "Avocats et coordonnées"}),
        "procedure": ("Procédure pénale", {"offence": "Qualification / faits reprochés", "court": "Juridiction", "police_unit": "Service enquêteur", "case_reference": "Références parquet / enquête", "custody": "Garde à vue / détention", "hearing": "Audiences et échéances", "appeal": "Voies de recours"}),
        "evidence": ("Pièces et demandes", {"evidence": "Pièces et preuves", "requests": "Demandes d'actes", "experts": "Expertises", "damages": "Préjudices / demandes civiles"}),
    },
    "contentieux-judiciaire": {
        "parties": ("Parties", {"claimant": "Demandeur", "defendant": "Défendeur", "third_parties": "Tiers / intervenants", "lawyers": "Avocats"}),
        "procedure": ("Procédure et juridiction", {"court": "Juridiction / chambre", "case_number": "N° RG / Portalis", "procedure_type": "Procédure", "filing_date": "Date de saisine", "hearings": "Audiences et calendrier", "decisions": "Décisions et recours"}),
        "claims": ("Demandes et pièces", {"claims": "Demandes principales et subsidiaires", "amounts": "Montants réclamés", "evidence": "Pièces / bordereau", "experts": "Expertise", "execution": "Exécution de la décision"}),
    },
    "commercial": {
        "parties": ("Parties et entreprises", {"client_entity": "Entreprise cliente", "counterparty": "Cocontractant / partie adverse", "contacts": "Contacts et représentants", "guarantors": "Garants / cautions"}),
        "contract": ("Contrats et relation commerciale", {"contract_type": "Type de contrat", "signature_date": "Date de signature", "term": "Durée / renouvellement", "termination": "Résiliation / préavis", "governing_law": "Droit applicable / juridiction"}),
        "dispute": ("Litige et créances", {"subject": "Objet du différend", "amounts": "Montants / factures", "deadlines": "Échéances", "evidence": "Pièces et échanges", "settlement": "Négociation / transaction"}),
    },
    "social": {
        "parties": ("Employeur et salarié", {"employer": "Employeur", "employee": "Salarié", "representatives": "Représentants / conseils", "contacts": "Contacts utiles"}),
        "employment": ("Relation de travail", {"job_title": "Emploi / classification", "contract_type": "Type et date du contrat", "seniority": "Ancienneté", "workplace": "Lieu de travail", "collective_agreement": "Convention collective", "salary": "Rémunération et avantages", "working_time": "Temps de travail"}),
        "procedure": ("Rupture et procédure", {"procedure_type": "Procédure / motif", "key_dates": "Dates clés", "letters": "Courriers et convocations", "claims": "Demandes et indemnités", "court": "Conseil de prud'hommes / juridiction", "evidence": "Pièces"}),
        "employees": ("Salariés", {"employee_list": "Liste des salariés concernés", "employee_count": "Effectif", "individual_records": "Informations individuelles utiles", "employee_status": "Statut et catégorie"}),
        "social_information": ("Informations sociales générales", {"employer_id": "Identifiants employeur", "establishments": "Établissements concernés", "collective_agreement_details": "Convention collective et IDCC", "payroll_context": "Paie et avantages", "social_calendar": "Échéances sociales"}),
        "representative_institutions": ("Institutions représentatives du personnel", {"union_representatives": "Représentants syndicaux", "social_economic_committee": "Membres du comité social et économique", "establishment_cse": "Membres du CSE d’établissement", "central_cse": "Membres du CSE central", "company_board": "Membres du conseil d’entreprise", "local_representatives": "Représentants de proximité", "other_representatives": "Autres représentants"}),
        "urssaf": ("Demandes URSSAF", {"urssaf_office": "Organisme / service URSSAF", "request_type": "Demande ou contrôle", "reference": "Référence du dossier", "period": "Période concernée", "amounts": "Cotisations et montants", "deadline": "Échéance de réponse", "correspondence": "Échanges et pièces"}),
        "labor_inspection": ("Déclarations inspection du travail", {"inspection_office": "Service compétent", "declaration_type": "Déclaration / signalement", "incident_date": "Date des faits", "response_deadline": "Échéance", "correspondence": "Courriers et réponses", "evidence": "Pièces justificatives"}),
        "contracts": ("Contrats", {"contract_types": "Contrats concernés", "contract_dates": "Dates de signature et d’effet", "amendments": "Avenants", "termination_terms": "Rupture / préavis", "contract_documents": "Documents contractuels"}),
        "litigation": ("Contentieux", {"dispute_subject": "Objet du contentieux", "court": "Juridiction", "case_reference": "Référence de procédure", "hearings": "Audiences et délais", "claims": "Demandes et montants", "evidence": "Pièces et preuves"}),
    },
    "fiscal": {
        "taxpayer": ("Contribuable", {"taxpayer_name": "Nom / dénomination", "tax_id": "Identifiant fiscal", "tax_address": "Adresse fiscale", "representatives": "Représentants"}),
        "tax_case": ("Impôt et période", {"tax_type": "Impôt / taxe", "period": "Période concernée", "tax_regime": "Régime fiscal", "amounts": "Montants / pénalités", "return_reference": "Déclaration / avis concerné"}),
        "procedure": ("Contrôle et recours", {"authority": "Administration / service", "notice_date": "Date de notification", "response_deadline": "Délai de réponse", "meetings": "Échanges / rendez-vous", "claims": "Réclamation / recours", "evidence": "Pièces justificatives"}),
        "tax_dashboard": ("Repères du dossier fiscal", {"created_on": "Date de création", "imported_documents": "Documents importés", "tax_regime": "Régime fiscal", "fiscal_stakes": "Enjeu fiscal", "fiscal_year": "Exercice"}),
        "tax_declarations": ("Déclarations IS/IR", {"declaration_type": "Déclaration (IS / IR / autre)", "taxpayer": "Contribuable concerné", "tax_year": "Année fiscale", "filing_deadline": "Date limite de dépôt", "filing_status": "État de la déclaration", "amount_due": "Impôt dû / crédit", "attachments": "Annexes et justificatifs"}),
        "tax_packages": ("Liasses fiscales", {"package_type": "Type de liasse", "fiscal_year": "Exercice", "accounting_period": "Période comptable", "forms": "Formulaires concernés", "figures_to_check": "Montants à vérifier", "submission_status": "État du dépôt"}),
        "tax_integration": ("Intégration fiscale", {"group_parent": "Société mère", "group_members": "Sociétés membres", "integration_start": "Début de l’intégration", "tax_consolidation": "Convention et calcul d’ensemble", "group_events": "Entrées / sorties du groupe"}),
        "tax_controls": ("Contrôle fiscal et vérifications", {"control_type": "Type de contrôle", "tax_authority": "Service vérificateur", "control_period": "Périodes vérifiées", "audit_start": "Début du contrôle", "audit_documents": "Documents demandés", "findings": "Constats / rectifications", "reply_deadline": "Délai de réponse"}),
        "tax_litigation": ("Contentieux fiscal", {"decision_contested": "Avis ou décision contestée", "claim_date": "Date de réclamation", "claim_arguments": "Moyens et demandes", "litigation_stage": "Étape de la procédure", "court": "Juridiction", "deadlines": "Délais et audiences"}),
        "tax_ruling": ("Optimisation & rescrit", {"question": "Question fiscale", "transaction": "Opération concernée", "legal_basis": "Fondement envisagé", "ruling_authority": "Administration saisie", "submission_date": "Date de saisine", "response_deadline": "Échéance de réponse", "response": "Réponse / position obtenue"}),
    },
    "notarie": {
        "parties": ("Parties et intervenants", {"parties": "Vendeur / acquéreur / donateur / bénéficiaires", "notary": "Notaire", "advisers": "Conseils et intervenants", "family_status": "État civil / situation familiale"}),
        "asset": ("Bien et opération", {"asset_description": "Désignation du bien", "address": "Adresse / références cadastrales", "price": "Prix / évaluation", "financing": "Financement", "conditions": "Conditions suspensives", "dates": "Dates et échéances"}),
        "deed": ("Acte et formalités", {"deed_type": "Type d'acte", "draft_status": "État du projet", "documents": "Pièces et diagnostics", "registrations": "Formalités / enregistrement", "succession": "Actifs, passifs et ayants droit"}),
    },
    "immobilier": {
        "parties": ("Preneur", {"tenant": "Preneur / locataire", "tenant_contacts": "Coordonnées et représentants du preneur"}),
        "guarantee": ("Caution", {"guarantor": "Caution / garant", "guarantee_type": "Type et étendue de la garantie", "guarantee_documents": "Acte et pièces de caution"}),
        "lease_transfer": ("Cession de droit au bail", {"assignor": "Cédant", "assignee": "Cessionnaire", "transfer_date": "Date envisagée / réalisée", "consent": "Agrément / autorisation", "transfer_price": "Prix et modalités"}),
        "lease": ("Bail", {"lease_type": "Type de bail", "landlord": "Bailleur", "signature_date": "Date de signature", "start_date": "Prise d'effet", "term": "Durée / échéance", "rent": "Loyer", "charges": "Charges", "revision": "Révision / indexation", "deposit": "Dépôt de garantie", "termination": "Congé / renouvellement"}),
        "premises": ("Locaux", {"address": "Adresse", "description": "Description / destination", "surface": "Surface", "lot_numbers": "Lots / références cadastrales", "condition": "État / travaux", "inventory": "État des lieux / diagnostics"}),
        "notice": ("Congé", {"notice_from": "Auteur du congé", "recipient": "Destinataire", "service_date": "Date et mode de notification", "effective_date": "Date d'effet", "grounds": "Motif", "dispute_deadline": "Délai / contestation"}),
        "real_property": ("Bien immobilier", {"identification": "Identification du bien", "title": "Titre de propriété", "cadastre": "Cadastre / parcelles", "diagnostics": "Diagnostics", "easements": "Servitudes", "mortgages": "Hypothèques"}),
        "transactions": ("Transactions", {"precontract": "Avant-contrat / compromis", "conditions": "Conditions suspensives", "financing": "Financement", "sale_deed": "Acte de vente", "vefa": "Vente en l’état futur d’achèvement (VEFA)"}),
        "urbanism": ("Urbanisme", {"building_permit": "Permis de construire", "prior_declaration": "Déclaration préalable", "planning_documents": "PLU / documents d’urbanisme", "appeals": "Recours", "demolition": "Démolition"}),
        "condominium": ("Copropriété", {"bylaws": "Règlement de copropriété", "meetings": "Assemblées générales", "property_manager": "Syndic", "charges": "Charges", "works": "Travaux"}),
        "lease_types": ("Baux", {"residential_lease": "Bail d’habitation", "commercial_lease": "Bail commercial", "professional_lease": "Bail professionnel", "leave_notice": "Congés et préavis", "unpaid_rent": "Loyers impayés"}),
    },
    "sport": {
        "people": ("Sportif et organisation", {"athlete": "Sportif", "club": "Club / employeur", "agent": "Agent", "federation": "Fédération / ligue"}),
        "contract": ("Contrat sportif", {"contract_type": "Type de contrat", "start_date": "Date de début", "end_date": "Date de fin", "compensation": "Rémunération / primes", "image_rights": "Droits à l'image", "exclusivity": "Exclusivité / obligations"}),
        "competition": ("Compétition et discipline", {"competition": "Compétition", "season": "Saison", "disciplinary_body": "Organe disciplinaire", "decision": "Décision contestée", "deadlines": "Délais et audiences", "evidence": "Pièces"}),
    },
    "agricole": {
        "parties": ("Exploitant et propriétaires", {"operator": "Exploitant", "landlord": "Bailleur / propriétaire", "company": "Structure agricole", "contacts": "Interlocuteurs"}),
        "holding": ("Exploitation et foncier", {"activity": "Activité / production", "parcels": "Parcelles et références", "buildings": "Bâtiments et équipements", "environmental": "Autorisations / contraintes environnementales"}),
        "lease_aid": ("Bail rural et aides", {"lease_type": "Type de bail", "term": "Durée / renouvellement", "rent": "Fermage", "subsidies": "Aides / subventions", "administration": "Organismes concernés", "dispute": "Litige / échéances"}),
        "farm_operations": ("Exploitations", {"operations": "Liste des exploitations", "parcels": "Parcellaire agricole", "crop_rotation": "Assolement", "farm_buildings": "Bâtiments agricoles"}),
        "conventions": ("Conventions", {"availability_agreements": "Conventions de mise à disposition", "rural_leases": "Baux ruraux", "sharefarming": "Fermage", "commodat": "Commodat / prêt à usage", "company_availability": "Mise à disposition à une société"}),
        "msa": ("MSA et cotisations", {"msa_statements": "Relevés MSA", "social_contributions": "Cotisations sociales", "msa_declarations": "Déclarations MSA"}),
        "pac_aids": ("PAC et aides", {"pac_declaration": "Déclaration PAC", "payment_entitlements": "Droits à paiement", "coupled_aid": "Aides couplées", "maec": "Mesures agro-environnementales et climatiques (MAEC)"}),
        "installation_transmission": ("Installation et transmission", {"installation": "Installation", "transmission": "Transmission d’exploitation", "safer": "SAFER et préemption"}),
        "environment": ("Environnement", {"environmental_permits": "Autorisations et contraintes", "environmental_proceedings": "Procédures environnementales"}),
        "rural_contention": ("Contentieux rural", {"dispute": "Objet du contentieux", "parties": "Parties concernées", "deadlines": "Délais et échéances", "evidence": "Pièces et preuves"}),
    },
    "transport": {
        "parties": ("Intervenants", {"shipper": "Expéditeur", "carrier": "Transporteur", "recipient": "Destinataire", "insurer": "Assureur"}),
        "shipment": ("Transport", {"transport_type": "Mode de transport", "goods": "Marchandises", "weight_value": "Poids / valeur déclarée", "origin": "Lieu de départ", "destination": "Destination", "dates": "Dates de prise en charge / livraison", "documents": "Lettre de voiture / connaissement"}),
        "incident": ("Incident et réclamation", {"incident_date": "Date de l'incident", "damage": "Perte / avarie / retard", "reservations": "Réserves et notifications", "claim_amount": "Montant réclamé", "deadlines": "Délais", "evidence": "Pièces et expertises"}),
    },
    "douane": {
        "operator": ("Opérateur", {"importer_exporter": "Importateur / exportateur", "customs_broker": "Représentant en douane", "eori": "N° EORI", "contacts": "Contacts"}),
        "goods_declaration": ("Marchandises et déclaration", {"goods": "Désignation / code douanier", "origin": "Origine / provenance", "customs_office": "Bureau de douane", "declaration_number": "N° de déclaration", "operation_date": "Date d'opération", "duties": "Droits / taxes"}),
        "control": ("Contrôle et recours", {"authority": "Autorité / service", "control_date": "Date de contrôle", "notice": "Notification / décision", "deadline": "Délai de réponse", "amounts": "Rappel / pénalités", "evidence": "Documents justificatifs"}),
    },
    "medical": {
        "people": ("Personnes et établissements", {"patient": "Patient / ayant droit", "practitioner": "Professionnel de santé", "establishment": "Établissement", "insurer": "Assureur", "opposing_parties": "Parties concernées"}),
        "care_event": ("Prise en charge et faits", {"care_dates": "Dates de soins", "facts": "Faits / dommage allégué", "injuries": "Préjudices", "medical_records": "Dossier médical / pièces", "complaint": "Réclamation / plainte"}),
        "expertise_procedure": ("Expertise et procédure", {"expert": "Expert", "expert_meetings": "Dates d'expertise", "court": "Juridiction / commission", "deadlines": "Délais", "claims": "Demandes et chiffrage"}),
    },
    "recouvrement": {
        "creditor_debtor": ("Créancier et débiteur", {"creditor": "Créancier", "debtor": "Débiteur", "guarantors": "Cautions / garants", "contacts": "Coordonnées"}),
        "claim": ("Créance", {"origin": "Origine de la créance", "invoices": "Factures / échéances", "principal": "Principal", "interest": "Intérêts / pénalités", "payments": "Règlements reçus", "dispute": "Contestations"}),
        "recovery": ("Démarches et exécution", {"reminders": "Relances et mises en demeure", "title": "Titre exécutoire", "bailiff": "Commissaire de justice", "enforcement": "Mesures d'exécution", "deadlines": "Délais / audiences", "costs": "Frais"}),
    },
    "patrimonial-famille": {
        "family": ("Situation familiale", {"spouses": "Époux / partenaires", "children": "Enfants et situation", "heirs": "Héritiers / bénéficiaires", "notary": "Notaire / conseils"}),
        "assets_liabilities": ("Patrimoine", {"real_estate": "Biens immobiliers", "accounts": "Comptes et placements", "business_assets": "Parts sociales / entreprises", "debts": "Dettes / emprunts", "valuations": "Évaluations et dates"}),
        "family_procedure": ("Procédure", {"marital_regime": "Régime matrimonial / union", "marriage_date": "Date et lieu de l'union", "separation_date": "Séparation / décès", "support": "Prestation / pension", "proceedings": "Procédure / ONC et juridiction", "deadlines": "Échéances", "orders_and_measures": "Ordonnances et mesures provisoires", "agreements": "Accords et conventions"}),
        "civil_status": ("État Civil", {"spouse_identity": "Identité des époux / partenaires", "birth_details": "Dates et lieux de naissance", "marriage_or_union": "Date et lieu du mariage / PACS", "marriage_contract": "Contrat de mariage", "family_documents": "Actes d’état civil et justificatifs"}),
        "property_liquidation": ("Patrimoine & Liquidation", {"assets_before_union": "Biens propres / antérieurs", "community_assets": "Biens communs / indivis", "liabilities": "Dettes et passif", "asset_valuations": "Évaluations des biens", "liquidation_proposal": "Projet de liquidation", "notary": "Notaire chargé de la liquidation"}),
        "children_authority": ("Enfants & Autorité Parentale", {"children_identity": "Identité et âge des enfants", "residence": "Résidence habituelle", "parental_authority": "Exercice de l’autorité parentale", "visitation": "Droit de visite et d’hébergement", "child_support": "Contribution à l’entretien", "child_needs": "Besoins et frais particuliers"}),
        "family_finances": ("Finances", {"income_by_party": "Ressources par partie", "monthly_expenses": "Charges mensuelles", "assets_and_debts": "Actif et passif", "support_calculation": "Éléments de calcul des pensions", "tax_position": "Situation fiscale"}),
        "family_tools": ("Outils et suivi", {"asset_schedule": "Tableau des biens et valeurs", "proposed_agreements": "Propositions d’accord", "missing_documents": "Documents manquants", "next_actions": "Prochaines démarches"}),
    },
    "personnes-protegees": {
        "protected_person": ("Personne protégée", {"identity": "Identité", "birth": "Date / lieu de naissance", "address": "Adresse", "health_context": "Éléments utiles communiqués", "relatives": "Proches / personnes à prévenir"}),
        "measure": ("Mesure et intervenants", {"measure_type": "Tutelle / curatelle / autre mesure", "representative": "Tuteur / curateur / mandataire", "judge": "Juge / juridiction", "decision_date": "Date de décision", "start_end": "Durée / renouvellement", "permissions": "Pouvoirs / autorisations"}),
        "assets_accounts": ("Patrimoine et comptes", {"inventory": "Inventaire des biens", "income": "Ressources", "expenses": "Charges", "accounts": "Comptes / opérations", "annual_report": "Comptes rendus de gestion", "deadlines": "Échéances"}),
    },
    "civil": {
        "parties": ("Parties", {"claimant": "Demandeur", "defendant": "Défendeur", "third_parties": "Tiers", "insurers": "Assureurs"}),
        "facts": ("Faits et obligations", {"relationship": "Relation / contrat", "events": "Chronologie", "breach": "Manquement / fait générateur", "damages": "Préjudices", "amounts": "Montants", "evidence": "Pièces"}),
        "procedure": ("Procédure", {"court": "Juridiction", "case_number": "N° de dossier", "acts": "Actes / décisions", "hearings": "Audiences / délais", "remedies": "Demandes / recours"}),
    },
    "ntic-propriete-intellectuelle": {
        "rights_holders": ("Titulaires et parties", {"rights_holder": "Titulaire des droits", "counterparty": "Partie adverse / utilisateur", "creators": "Auteurs / inventeurs", "platforms": "Plateformes concernées"}),
        "protected_assets": ("Œuvre, marque ou technologie", {"asset_type": "Type d'actif", "title": "Titre / description", "registration": "Dépôt / enregistrement", "territory": "Territoire", "ownership": "Chaîne de titularité", "licence": "Licence / cession"}),
        "digital_case": ("Données et contentieux numérique", {"systems": "Systèmes / services", "personal_data": "Données personnelles en cause", "incident_date": "Date / durée", "infringement": "Atteinte alléguée", "evidence": "Constats / preuves", "remedies": "Mesures demandées"}),
    },
    "esport": {
        "participants": ("Joueur et structure", {"player": "Joueur", "team": "Équipe / organisation", "publisher": "Éditeur du jeu", "agent": "Agent / représentant"}),
        "competition_contract": ("Contrat et compétition", {"game": "Jeu", "competition": "Compétition / saison", "contract_type": "Type de contrat", "term": "Durée", "compensation": "Rémunération / gains", "sponsorship": "Sponsors"}),
        "digital_rights_dispute": ("Droits et litige", {"image_rights": "Image / diffusion", "transfer": "Transfert", "discipline": "Règlement / sanction", "body": "Fédération / organe compétent", "deadlines": "Délais", "evidence": "Pièces"}),
    },
    "aerien": {
        "passengers": ("Passager et réservation", {"passengers": "Passagers", "airline": "Compagnie aérienne", "booking_reference": "Référence de réservation", "ticket_numbers": "N° de billets", "travel_agency": "Agence / intermédiaire"}),
        "flight": ("Vol", {"flight_number": "N° de vol", "route": "Trajet", "scheduled_times": "Horaires prévus", "actual_times": "Horaires réels", "disruption": "Retard / annulation / refus d'embarquement", "baggage": "Bagages"}),
        "claim": ("Réclamation et préjudice", {"claim_date": "Date de réclamation", "response": "Réponse de la compagnie", "expenses": "Frais engagés", "injury": "Préjudice / dommage", "insurer": "Assureur", "deadlines": "Délais / procédure"}),
    },
    "administratif": {
        "administration": ("Administration et administré", {"authority": "Administration / organisme", "applicant": "Administré / entreprise", "contacts": "Interlocuteurs", "contractors": "Cocontractants / tiers"}),
        "decision_contract": ("Décision ou contrat public", {"decision_type": "Type de décision", "decision_date": "Date de décision / notification", "public_contract": "Marché / concession", "procurement_reference": "Référence de consultation", "amounts": "Montants", "territory": "Commune / périmètre"}),
        "administrative_procedure": ("Recours et procédure", {"recourse_type": "Recours / référé", "court": "Juridiction", "filing_deadline": "Délai de recours", "prior_claim": "Recours préalable", "evidence": "Pièces", "remedies": "Conclusions / mesures demandées"}),
    },
}


def _matter_profile(value):
    if not isinstance(value, dict) or len(value) > 40:
        raise ValueError("La fiche dossier doit être un objet de rubriques valide")
    cleaned, total = {}, 0
    for section, fields in value.items():
        section = _legal_text(section, required=True, limit=80)
        if not isinstance(fields, dict) or len(fields) > 80:
            raise ValueError("Rubrique de fiche dossier invalide")
        cleaned[section] = {}
        for key, text in fields.items():
            key = _legal_text(key, required=True, limit=100)
            if not isinstance(text, str) or len(text) > 20_000:
                raise ValueError("Chaque information doit être un texte de 20 000 caractères maximum")
            cleaned[section][key] = text.strip()
            total += len(text)
    if total > 250_000:
        raise ValueError("La fiche dossier dépasse 250 000 caractères")
    return cleaned


def _matter_profile_schema(domain_id):
    sections = dict(COMMON_MATTER_PROFILE)
    if domain_id == "societes":
        sections.update(SOCIETY_PROFILE_LABELS)
    else:
        sections.update(DOMAIN_MATTER_PROFILE.get(domain_id, {}))
    return [{"id": section, "label": label, "fields": [{"id": key, "label": field_label} for key, field_label in fields.items()]}
            for section, (label, fields) in sections.items()]


def _matter_profile_lines(profile, schema):
    lines = []
    labels = {section["id"]: (section["label"], {field["id"]: field["label"] for field in section["fields"]}) for section in schema}
    for section, fields in profile.items():
        section_label, field_labels = labels.get(section, (section.replace("_", " ").title(), {}))
        values = [(field_labels.get(key, key.replace("_", " ").capitalize()), value) for key, value in fields.items() if value]
        if values:
            lines.append(f"### {section_label}")
            lines.extend(f"- **{label} :** {value}" for label, value in values)
    return lines


def _legal_round(value):
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def legal_snapshot(conn, project_id):
    workspace = conn.execute("SELECT domain, matter_types FROM legal_workspaces WHERE project_id=?", (project_id,)).fetchone()
    result = {"project_id": project_id, "domain": workspace["domain"] if workspace else None,
              "matter_types": json.loads(workspace["matter_types"]) if workspace else [],
              "domains": list(LEGAL_DOMAINS)}
    result["matter_profile_schema"] = _matter_profile_schema(result["domain"])
    # Retained as a wire alias for clients released before the matter-profile generalization.
    result["company_profile_schema"] = result["matter_profile_schema"]
    for key in ("clients", "matters", "acts", "fees", "fee_codes", "subscriptions", "documents", "payments"):
        rows = conn.execute(f"SELECT * FROM legal_{key} WHERE project_id=? ORDER BY rowid", (project_id,)).fetchall()
        result[key] = [{k: row[k] for k in row.keys() if k != "project_id"} for row in rows]
    for matter in result["matters"]:
        profile = json.loads(matter.get("matter_profile") or "{}")
        if not profile:
            profile = json.loads(matter.get("company_profile") or "{}")
        matter["matter_profile"] = profile
        matter["company_profile"] = profile
    for document in result["documents"]:
        document["snapshot"] = json.loads(document["snapshot"])
        document["paid_cents"] = sum(p["amount_cents"] for p in result["payments"] if p["document_id"] == document["id"])
        credited = sum(d["total_cents"] for d in result["documents"] if d.get("related_document_id") == document["id"])
        document["credited_cents"] = credited
        document["balance_cents"] = max(0, document["total_cents"] - document["paid_cents"] - credited)
        document["cancelled"] = document["kind"] == "invoice" and credited >= document["total_cents"]
        document["refund_due_cents"] = max(0, document["paid_cents"] + credited - document["total_cents"])
    settings = conn.execute("SELECT * FROM legal_firm_settings WHERE id=1").fetchone()
    result["firm_settings"] = {k: settings[k] for k in settings.keys() if k != "id"} if settings else {
        "jurisdiction": "FR", "legal_name": "", "address": "", "siren": "", "vat_number": "",
        "vat_regime": "standard", "bar_name": "", "payment_delay_days": 30,
        "late_penalty_rate": "3 fois le taux d’intérêt légal",
    }
    # The profile database is the cabinet boundary. These totals consolidate its projects,
    # while the detail lists above remain scoped to the selected project.
    result["firm_totals"] = _firm_totals(conn)
    drafts = conn.execute("SELECT * FROM legal_practice_documents WHERE project_id=? ORDER BY rowid", (project_id,)).fetchall()
    result["practice_documents"] = [{**{k: row[k] for k in row.keys() if k not in ("project_id", "fee_ids")}, "fee_ids": json.loads(row["fee_ids"])} for row in drafts]
    result["practice_document_templates"] = [{"id": key, "label": label} for key, label in LEGAL_PRACTICE_DOCUMENT_TEMPLATES]
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
    template_id = snapshot.get("template_id", "classique")
    purpose_labels = {
        "provision_fees": "Facture de provision sur honoraires",
        "provision_expenses_fees": "Facture de provision sur frais et honoraires",
    }
    title = "Avoir d'annulation" if document["kind"] == "credit_note" else purpose_labels.get(document.get("purpose"), "Facture" if is_invoice else "Devis")
    template_titles = {
        "classique": "Présentation classique",
        "synthese": "Présentation synthèse",
        "detaille": "Présentation détaillée",
    }
    lines = [
        f"# {title} — BROUILLON À RELIRE",
        f"_{template_titles.get(template_id, template_titles['classique'])}_",
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
    lines.extend(["", "## Dossier", f"{cell(matter['title'])}" + (f" — réf. {cell(matter['reference'])}" if matter.get("reference") else "")])
    company = matter.get("matter_profile", matter.get("company_profile", {})).get("company_details", {})
    company_fields = [(label, company.get(key)) for key, label in (("registered_name", "Dénomination sociale"), ("legal_form", "Forme juridique"), ("registered_office", "Siège social"), ("registration_number", "RCS / registre"), ("siren", "SIREN"), ("siret", "SIRET"), ("vat_number", "N° TVA")) if company.get(key)]
    if company_fields:
        lines.extend(["", "### Société concernée par le dossier"])
        lines.extend(f"- {label} : {cell(value)}" for label, value in company_fields)
    if template_id == "synthese":
        lines.extend(["", "## Prestations", ""])
        for item in snapshot["lines"]:
            lines.append(
                f"- **{cell(item['description'])}** — {money(item['net_cents'])} HT, "
                f"TVA {item['tax_bps'] / 100:g} % ({money(item['tax_cents'])}), "
                f"soit {money(item['net_cents'] + item['tax_cents'])} TTC"
            )
    elif template_id == "detaille":
        lines.extend(["", "## Détail des prestations", "",
                      "| Prestation | Montant HT | Taux TVA | TVA | Montant TTC |",
                      "|---|---:|---:|---:|---:|"])
        for item in snapshot["lines"]:
            lines.append(
                f"| {cell(item['description'])} | {money(item['net_cents'])} | "
                f"{item['tax_bps'] / 100:g} % | {money(item['tax_cents'])} | "
                f"{money(item['net_cents'] + item['tax_cents'])} |"
            )
    else:
        lines.extend(["", "## Honoraires", ""])
        for item in snapshot["lines"]:
            lines.append(
                f"- {cell(item['description'])} : {money(item['net_cents'])} HT "
                f"(TVA {item['tax_bps'] / 100:g} % : {money(item['tax_cents'])})"
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
      COALESCE(SUM(CASE WHEN f.billable=1 THEN f.net_cents ELSE 0 END),0) AS fees_cents,COUNT(f.id) AS fee_count
      FROM projects p LEFT JOIN legal_fees f ON f.project_id=p.id
      GROUP BY p.id,p.name ORDER BY p.name""").fetchall()
    by_user = conn.execute("""SELECT COALESCE(NULLIF(f.responsible_user,''),'Non attribué') AS user,
      COALESCE(SUM(CASE WHEN f.billable=1 THEN f.net_cents ELSE 0 END),0) AS fees_cents,COUNT(f.id) AS fee_count
      FROM legal_fees f GROUP BY COALESCE(NULLIF(f.responsible_user,''),'Non attribué')
      ORDER BY user""").fetchall()
    by_matter = conn.execute("""SELECT m.project_id,p.name AS project,m.id AS matter_id,m.title,
      COALESCE(SUM(CASE WHEN f.billable=1 THEN f.net_cents ELSE 0 END),0) AS fees_cents,COUNT(f.id) AS fee_count
      FROM legal_matters m JOIN projects p ON p.id=m.project_id
      LEFT JOIN legal_fees f ON f.matter_id=m.id AND f.project_id=m.project_id
      GROUP BY m.project_id,p.name,m.id,m.title ORDER BY p.name,m.title""").fetchall()
    totals = conn.execute("""SELECT COALESCE(SUM(CASE WHEN billable=1 THEN net_cents ELSE 0 END),0) AS fees_cents,
      COUNT(*) AS fee_count FROM legal_fees""").fetchone()
    docs = conn.execute("""SELECT COALESCE(SUM(CASE WHEN d.kind='invoice' THEN d.total_cents WHEN d.kind='credit_note' THEN -d.total_cents ELSE 0 END),0) AS invoiced_cents,
      COALESCE((SELECT SUM(amount_cents) FROM legal_payments),0) AS paid_cents
      FROM legal_documents d WHERE d.kind IN ('invoice','credit_note')""").fetchone()
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
        if action in ("fee.add", "fee_code.save", "subscription.save", "subscription.invoice", "practice_document.create", "document.create", "payment.add", "payment.allocate", "document.credit"):
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
        previous_matter = None
        if p.get("id"):
            existing = _legal_row(conn, table, pid, row_id)
            if action == "matter.save":
                previous_matter = existing
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
            if "matter_profile" in p or "company_profile" in p:
                profile = _matter_profile(p.get("matter_profile", p.get("company_profile")))
                if previous_matter:
                    prior = json.loads(previous_matter.get("matter_profile") or "{}")
                    if not prior:
                        prior = json.loads(previous_matter.get("company_profile") or "{}")
                    profile = {**prior, **{section: {**prior.get(section, {}), **fields} for section, fields in profile.items()}}
                values["matter_profile"] = json.dumps(profile, ensure_ascii=False)
                values["company_profile"] = values["matter_profile"]
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
        if kind not in ("fixed", "time", "expense"):
            raise ValueError("Type d'honoraires invalide")
        minutes = _legal_integer(p.get("minutes", 0), high=1_000_000)
        rate = _legal_integer(p.get("rate_cents", 0))
        net = _legal_round(Decimal(minutes) * rate / 60) if kind == "time" else _legal_integer(p.get("amount_cents", 0))
        if net <= 0 or (kind == "time" and (minutes == 0 or rate == 0)):
            raise ValueError("Honoraires strictement positifs requis")
        _legal_integer(net)
        tax_bps = _legal_integer(p.get("tax_bps", 0), high=10000)
        tax = _legal_round(Decimal(net) * tax_bps / 10000)
        billing_code = _legal_text(p.get("billing_code"), limit=40)
        activity_type = _legal_text(p.get("activity_type"), limit=40)
        activity_date = _legal_date(p.get("activity_date") or date.today().isoformat())
        if activity_date > date.today().isoformat():
            raise ValueError("Une activité déjà réalisée ne peut pas être datée dans le futur")
        if billing_code and not conn.execute("SELECT 1 FROM legal_fee_codes WHERE project_id=? AND code=?", (pid, billing_code)).fetchone():
            raise ValueError("Code de facturation inconnu dans le cabinet")
        billable = p.get("billable", True)
        if type(billable) is not bool:
            raise ValueError("Le statut facturable doit être vrai ou faux")
        conn.execute("INSERT INTO legal_fees (id,project_id,matter_id,description,kind,minutes,rate_cents,net_cents,tax_bps,tax_cents,invoice_id,responsible_user,activity_date,billing_code,activity_type,billable) VALUES (?,?,?,?,?,?,?,?,?,?,NULL,?,?,?,?,?)", (secrets.token_hex(16), pid, p["matter_id"], _legal_text(p.get("description"), required=True), kind, minutes, rate, net, tax_bps, tax, _legal_text(p.get("responsible_user"), limit=200), activity_date, billing_code, activity_type, int(billable)))
        return
    if action == "fee_code.save":
        code = _legal_text(p.get("code"), required=True, limit=40)
        label = _legal_text(p.get("label"), required=True, limit=120)
        hourly = _legal_integer(p.get("hourly_rate_cents", 0))
        fixed = _legal_integer(p.get("fixed_amount_cents", 0))
        tax_bps = _legal_integer(p.get("tax_bps", 0), high=10000)
        if p.get("id"):
            _legal_row(conn, "legal_fee_codes", pid, p["id"])
            conn.execute("UPDATE legal_fee_codes SET code=?,label=?,hourly_rate_cents=?,fixed_amount_cents=?,tax_bps=? WHERE id=? AND project_id=?", (code, label, hourly, fixed, tax_bps, p["id"], pid))
        else:
            current = conn.execute("SELECT id FROM legal_fee_codes WHERE project_id=? AND code=?", (pid, code)).fetchone()
            if current:
                conn.execute("UPDATE legal_fee_codes SET label=?,hourly_rate_cents=?,fixed_amount_cents=?,tax_bps=? WHERE id=?", (label, hourly, fixed, tax_bps, current["id"]))
            else:
                conn.execute("INSERT INTO legal_fee_codes (id,project_id,code,label,hourly_rate_cents,fixed_amount_cents,tax_bps) VALUES (?,?,?,?,?,?,?)", (secrets.token_hex(16), pid, code, label, hourly, fixed, tax_bps))
        return
    if action == "subscription.save":
        matter = _legal_row(conn, "legal_matters", pid, p.get("matter_id"))
        cadence = p.get("cadence")
        if cadence not in ("monthly", "semiannual", "annual"):
            raise ValueError("Périodicité d'abonnement invalide")
        starts_on = _legal_date(p.get("starts_on"))
        next_on = _legal_date(p.get("next_invoice_on") or starts_on)
        ends_on = _legal_date(p["ends_on"]) if p.get("ends_on") else ""
        if next_on < starts_on or (ends_on and ends_on < next_on):
            raise ValueError("Dates d'abonnement incohérentes")
        amount = _legal_integer(p.get("amount_cents"), low=1)
        tax_bps = _legal_integer(p.get("tax_bps", 0), high=10000)
        status = p.get("status", "active")
        if status not in ("active", "paused", "ended"):
            raise ValueError("Statut d'abonnement invalide")
        sub_id = p.get("id") or secrets.token_hex(16)
        if p.get("id"):
            _legal_row(conn, "legal_subscriptions", pid, sub_id)
            conn.execute("UPDATE legal_subscriptions SET matter_id=?,label=?,amount_cents=?,tax_bps=?,cadence=?,starts_on=?,ends_on=?,next_invoice_on=?,status=? WHERE id=? AND project_id=?", (matter["id"], _legal_text(p.get("label"), required=True, limit=200), amount, tax_bps, cadence, starts_on, ends_on, next_on, status, sub_id, pid))
        else:
            conn.execute("INSERT INTO legal_subscriptions VALUES (?,?,?,?,?,?,?,?,?,?,?)", (sub_id, pid, matter["id"], _legal_text(p.get("label"), required=True, limit=200), amount, tax_bps, cadence, starts_on, ends_on, next_on, status))
        return
    if action == "subscription.invoice":
        sub = _legal_row(conn, "legal_subscriptions", pid, p.get("subscription_id"))
        if sub["status"] != "active":
            raise ValueError("Cet abonnement n'est pas actif")
        period = sub["next_invoice_on"]
        if period > date.today().isoformat():
            raise ValueError("La prochaine échéance de cet abonnement n'est pas encore atteinte")
        if sub["ends_on"] and period > sub["ends_on"]:
            raise ValueError("L'abonnement est arrivé à son terme")
        matter = _legal_row(conn, "legal_matters", pid, sub["matter_id"])
        client = _legal_row(conn, "legal_clients", pid, matter["client_id"])
        settings = conn.execute("SELECT * FROM legal_firm_settings WHERE id=1").fetchone()
        if not settings or not settings["legal_name"] or not settings["address"] or not settings["siren"] or (settings["vat_regime"] == "standard" and not settings["vat_number"]):
            raise ValueError("Complétez les paramètres de facturation avant de générer la facture")
        if not client["address"].strip() or (client["customer_type"] == "professional" and len(client["siren"]) != 9):
            raise ValueError("Complétez l'adresse du client et son SIREN professionnel avant la facture")
        if settings["vat_regime"] == "franchise" and sub["tax_bps"]:
            raise ValueError("La franchise en base ne peut pas facturer de TVA")
        net = sub["amount_cents"]
        tax = _legal_round(Decimal(net) * sub["tax_bps"] / 10000)
        fee_id, doc_id = secrets.token_hex(16), secrets.token_hex(16)
        description = f"Abonnement {sub['label']} — période du {period}"
        conn.execute("INSERT INTO legal_fees (id,project_id,matter_id,description,kind,minutes,rate_cents,net_cents,tax_bps,tax_cents,invoice_id,responsible_user,activity_date,billing_code,activity_type,billable) VALUES (?,?,?,?,?,?,?,?,?,?,NULL,'',?,'','subscription',1)", (fee_id, pid, matter["id"], description, "fixed", 0, 0, net, sub["tax_bps"], tax, period))
        count = conn.execute("SELECT COUNT(*) FROM legal_documents WHERE kind='invoice'").fetchone()[0] + 1
        ref = f"FAC-BROUILLON-{date.today().year}-{count:05d}"
        due_on = max(period, date.today().isoformat())
        template_id = p.get("template_id", "classique")
        if template_id not in ("classique", "synthese", "detaille"):
            raise ValueError("Modèle de document inconnu")
        snapshot = {"client": {k: client[k] for k in ("name", "email", "address", "customer_type", "siren")}, "matter": {k: matter[k] for k in ("title", "reference")}, "lines": [{"description": description, "net_cents": net, "tax_bps": sub["tax_bps"], "tax_cents": tax}], "template_id": template_id, "purpose": "subscription", "jurisdiction": "FR", "issuer": {k: settings[k] for k in ("legal_name", "address", "siren", "vat_number", "vat_regime", "bar_name")}, "payment_terms": {"due_on": due_on, "delay_days": settings["payment_delay_days"], "late_penalty_rate": settings["late_penalty_rate"], "recovery_indemnity_cents": 4000}, "vat_notice": "TVA non applicable, article 293 B du CGI" if settings["vat_regime"] == "franchise" else ""}
        conn.execute("INSERT INTO legal_documents (id,project_id,matter_id,kind,reference,created_on,due_on,snapshot,net_cents,tax_cents,total_cents,purpose,related_document_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL)", (doc_id, pid, matter["id"], "invoice", ref, date.today().isoformat(), due_on, json.dumps(snapshot, ensure_ascii=False), net, tax, net + tax, "subscription"))
        conn.execute("UPDATE legal_fees SET invoice_id=? WHERE id=?", (doc_id, fee_id))
        from datetime import date as _date
        from calendar import monthrange
        months = {"monthly": 1, "semiannual": 6, "annual": 12}[sub["cadence"]]
        year, month = int(period[:4]), int(period[5:7])
        month += months
        year += (month - 1) // 12
        month = (month - 1) % 12 + 1
        day = min(int(sub["starts_on"][8:10]), monthrange(year, month)[1])
        next_on = _date(year, month, day).isoformat()
        status = "ended" if sub["ends_on"] and next_on > sub["ends_on"] else "active"
        conn.execute("UPDATE legal_subscriptions SET next_invoice_on=?,status=? WHERE id=?", (next_on, status, sub["id"]))
        return
    if action == "practice_document.create":
        matter = _legal_row(conn, "legal_matters", pid, p.get("matter_id"))
        client = _legal_row(conn, "legal_clients", pid, matter["client_id"])
        template = next(((key, label) for key, label in LEGAL_PRACTICE_DOCUMENT_TEMPLATES if key == p.get("template_id")), None)
        if not template:
            raise ValueError("Modèle de document juridique inconnu")
        ids = p.get("fee_ids") or []
        if len(ids) != len(set(ids)) or len(ids) > 500:
            raise ValueError("Sélection de lignes de facturation invalide")
        fees = [_legal_row(conn, "legal_fees", pid, fee_id) for fee_id in ids]
        if any(item["matter_id"] != matter["id"] for item in fees):
            raise ValueError("Les lignes doivent appartenir au dossier sélectionné")
        title = _legal_text(p.get("title") or template[1], required=True, limit=200)
        lines = [f"# {title} — BROUILLON À RELIRE", "", f"Date : {date.today().strftime('%d/%m/%Y')}",
                 f"Client : {client['name']}", f"Dossier : {matter['title']} ({matter['reference']})", "",
                 "## Objet", f"{template[1]} lié au dossier {matter['reference'] or matter['title']}.", "",
                 "## Informations et pièces à compléter", "- Vérifier les faits, dates, montants et destinataires.",
                 "- Ajouter les pièces justificatives et les mentions propres à ce document."]
        profile = json.loads(matter.get("matter_profile") or matter.get("company_profile") or "{}")
        profile_lines = _matter_profile_lines(profile, legal_snapshot(conn, pid)["matter_profile_schema"])
        if profile_lines:
            lines.extend(["", "## Informations société du dossier — à vérifier", *profile_lines])
        if fees:
            lines.extend(["", "## Lignes de facturation associées"])
            for item in fees:
                lines.append(f"- {item['activity_date']} · {item['billing_code']} · {item['description']} · {item['net_cents'] / 100:.2f} € HT")
        lines.extend(["", "BROUILLON INTERNE. Ce modèle de départ ne remplace pas les pièces ou mentions propres au document ; contrôler et compléter avant usage."])
        conn.execute("INSERT INTO legal_practice_documents (id,project_id,matter_id,template_id,title,body,fee_ids,created_on) VALUES (?,?,?,?,?,?,?,?)", (secrets.token_hex(16), pid, matter["id"], template[0], title, "\n".join(lines), json.dumps(ids), date.today().isoformat()))
        return
    if action == "document.create":
        matter = _legal_row(conn, "legal_matters", pid, p.get("matter_id"))
        client = _legal_row(conn, "legal_clients", pid, matter["client_id"])
        kind = p.get("kind")
        if kind not in ("quote", "invoice"):
            raise ValueError("Type de document invalide")
        template_id = p.get("template_id", "classique")
        if template_id not in ("classique", "synthese", "detaille"):
            raise ValueError("Modèle de document inconnu")
        settings = conn.execute("SELECT * FROM legal_firm_settings WHERE id=1").fetchone()
        if kind == "invoice" and (not settings or not settings["legal_name"] or not settings["address"] or not settings["siren"] or (settings["vat_regime"] == "standard" and not settings["vat_number"])):
            raise ValueError("Renseignez l’identité, l’adresse, le SIREN et, si le cabinet est assujetti, le numéro de TVA dans les paramètres de facturation.")
        ids = p.get("fee_ids") or []
        if not ids or len(ids) != len(set(ids)) or len(ids) > 500:
            raise ValueError("Sélectionner entre 1 et 500 honoraires distincts")
        fees = [_legal_row(conn, "legal_fees", pid, fee_id) for fee_id in ids]
        if kind == "invoice" and (not client["address"].strip() or (client["customer_type"] == "professional" and len(client["siren"]) != 9)):
            raise ValueError("Complétez l’adresse du client et, pour un client professionnel, son SIREN avant la facture.")
        if any(f["matter_id"] != matter["id"] or not f["billable"] or (kind == "invoice" and f["invoice_id"]) for f in fees):
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
        matter_profile = json.loads(matter.get("matter_profile") or matter.get("company_profile") or "{}")
        snapshot = {"client": {k: client[k] for k in ("name", "email", "address", "customer_type", "siren")}, "matter": {**{k: matter[k] for k in ("title", "reference", "matter_type")}, "matter_profile": matter_profile, "company_profile": matter_profile}, "lines": [{k: f[k] for k in ("description", "net_cents", "tax_bps", "tax_cents")} for f in fees], "template_id": template_id}
        if kind == "invoice":
            snapshot["jurisdiction"] = "FR"
            snapshot["issuer"] = {k: settings[k] for k in ("legal_name", "address", "siren", "vat_number", "vat_regime", "bar_name")}
            snapshot["payment_terms"] = {"due_on": due_on, "delay_days": settings["payment_delay_days"],
                "late_penalty_rate": settings["late_penalty_rate"], "recovery_indemnity_cents": 4000}
            snapshot["vat_notice"] = "TVA non applicable, article 293 B du CGI" if settings["vat_regime"] == "franchise" else ""
        purpose = p.get("purpose", "standard")
        if purpose not in ("standard", "provision_fees", "provision_expenses_fees"):
            raise ValueError("Type de facture inconnu")
        if kind != "invoice" and purpose != "standard":
            raise ValueError("Les provisions concernent les factures")
        snapshot["purpose"] = purpose
        conn.execute("INSERT INTO legal_documents (id,project_id,matter_id,kind,reference,created_on,due_on,snapshot,net_cents,tax_cents,total_cents,purpose,related_document_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL)", (doc_id, pid, matter["id"], kind, ref, today, due_on, json.dumps(snapshot, ensure_ascii=False), net, tax, net + tax, purpose))
        if kind == "invoice":
            conn.executemany("UPDATE legal_fees SET invoice_id=? WHERE id=? AND project_id=?", [(doc_id, f["id"], pid) for f in fees])
        return
    if action == "document.credit":
        original = _legal_row(conn, "legal_documents", pid, p.get("document_id"))
        if original["kind"] != "invoice":
            raise ValueError("Un avoir doit référencer une facture")
        credited = conn.execute("SELECT COALESCE(SUM(total_cents),0) FROM legal_documents WHERE project_id=? AND kind='credit_note' AND related_document_id=?", (pid, original["id"])).fetchone()[0]
        if credited >= original["total_cents"]:
            raise ValueError("Cette facture est déjà entièrement annulée par un avoir")
        reason = _legal_text(p.get("reason"), required=True, limit=500)
        today = date.today().isoformat()
        doc_id = secrets.token_hex(16)
        count = conn.execute("SELECT COUNT(*) FROM legal_documents WHERE kind='credit_note'").fetchone()[0] + 1
        ref = f"AVO-BROUILLON-{date.today().year}-{count:05d}"
        snapshot = json.loads(original["snapshot"])
        snapshot["credit_reason"] = reason
        snapshot["credited_invoice_reference"] = original["reference"]
        snapshot["purpose"] = "annulation"
        conn.execute("INSERT INTO legal_documents (id,project_id,matter_id,kind,reference,created_on,due_on,snapshot,net_cents,tax_cents,total_cents,purpose,related_document_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", (doc_id, pid, original["matter_id"], "credit_note", ref, today, today, json.dumps(snapshot, ensure_ascii=False), original["net_cents"], original["tax_cents"], original["total_cents"] - credited, "annulation", original["id"]))
        return
    if action == "payment.allocate":
        amount = _legal_integer(p.get("amount_cents"), low=1)
        paid_on = _legal_date(p.get("paid_on"))
        if paid_on > date.today().isoformat():
            raise ValueError("Un règlement reçu ne peut pas être daté dans le futur")
        reference = _legal_text(p.get("reference"), required=True)
        allocations = p.get("allocations") or []
        if not allocations or len(allocations) > 100:
            raise ValueError("Affecter le règlement à au moins une facture")
        seen = set()
        allocated = 0
        for allocation in allocations:
            doc = _legal_row(conn, "legal_documents", pid, allocation.get("document_id"))
            if doc["kind"] != "invoice" or doc["id"] in seen:
                raise ValueError("Chaque facture doit être sélectionnée une seule fois")
            seen.add(doc["id"])
            part = _legal_integer(allocation.get("amount_cents"), low=1)
            previous = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM legal_payments WHERE document_id=?", (doc["id"],)).fetchone()[0]
            credits = conn.execute("SELECT COALESCE(SUM(total_cents),0) FROM legal_documents WHERE kind='credit_note' AND related_document_id=?", (doc["id"],)).fetchone()[0]
            if part > max(0, doc["total_cents"] - previous - credits):
                raise ValueError("Une affectation dépasse le solde de la facture")
            allocated += part
        if allocated != amount:
            raise ValueError("La somme des affectations doit correspondre exactement au règlement reçu")
        conn.executemany("INSERT INTO legal_payments VALUES (?,?,?,?,?,?)", [(secrets.token_hex(16), pid, allocation["document_id"], allocation["amount_cents"], paid_on, reference) for allocation in allocations])
        return
    if action == "payment.add":
        doc = _legal_row(conn, "legal_documents", pid, p.get("document_id"))
        if doc["kind"] != "invoice":
            raise ValueError("Enregistrer un règlement sur une facture de travail")
        amount = _legal_integer(p.get("amount_cents"), low=1)
        paid = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM legal_payments WHERE document_id=?", (doc["id"],)).fetchone()[0]
        credits = conn.execute("SELECT COALESCE(SUM(total_cents),0) FROM legal_documents WHERE kind='credit_note' AND related_document_id=?", (doc["id"],)).fetchone()[0]
        if amount > max(0, doc["total_cents"] - paid - credits):
            raise ValueError("Le règlement dépasse le solde")
        paid_on = _legal_date(p.get("paid_on"))
        if paid_on > date.today().isoformat():
            raise ValueError("Un règlement reçu ne peut pas être daté dans le futur")
        conn.execute("INSERT INTO legal_payments VALUES (?,?,?,?,?,?)", (secrets.token_hex(16), pid, doc["id"], amount, paid_on, _legal_text(p.get("reference"), required=True)))
        return
    raise ValueError("Opération juridique inconnue")

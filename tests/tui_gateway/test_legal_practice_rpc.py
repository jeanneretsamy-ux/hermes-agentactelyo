"""Real project/RPC/SQLite boundaries: billing arithmetic, retry safety and profile ownership."""
from datetime import date, timedelta

import pytest

from hermes_constants import reset_hermes_home_override, set_hermes_home_override
from tui_gateway import server
from tui_gateway.contracts.registry import METHODS


def call(method, **params):
    contract = METHODS[method]
    validated = contract.params.model_validate(params).model_dump()
    response = server._methods[method](1, validated)
    assert "error" not in response, response
    contract.result.model_validate(response["result"])
    return response["result"]


def fail(method, **params):
    result = server._methods[method](1, params)
    assert result["error"]["code"] == 5063, result


def test_legal_workflow_money_snapshot_and_retry_are_durable(tmp_path):
    pid = call("projects.create", name="Droit social", folders=[str(tmp_path)])["project"]["id"]
    p = {"project_id": pid}
    call("legal.workspace.set", **p, domain="social")
    call("legal.firm.settings.set", **p, legal_name="Cabinet Test", address="1 rue Test, Paris",
         siren="123456789", vat_number="FR00123456789", vat_regime="standard", bar_name="Paris")
    client = call("legal.client.save", **p, name="Client témoin", address="10 rue Test", email="test@example.test")["clients"][0]
    matter = call("legal.matter.save", **p, client_id=client["id"], title="Rupture", matter_type="Rupture du contrat", reference="SOC-01")["matters"][0]
    act = call("legal.act.save", **p, title="Modèle personnel", act_type="Avenant", body="Client : {{client}}")["acts"][0]
    call("legal.act.save", **p, **{**act, "body": "Dossier : {{dossier}}"})
    fee_params = {**p, "request_id": "fee-1", "matter_id": matter["id"], "description": "Consultation", "kind": "time", "minutes": 25, "rate_cents": 19999, "tax_bps": 2000, "responsible_user": "Avocate A"}
    fee = call("legal.fee.add", **fee_params)["fees"][0]
    assert fee["net_cents"] == 8333
    assert fee["tax_cents"] == 1667
    assert fee["responsible_user"] == "Avocate A"
    assert len(call("legal.fee.add", **fee_params)["fees"]) == 1
    fail("legal.fee.add", **{**fee_params, "description": "Changed retry"})
    fail("legal.fee.add", **{**fee_params, "request_id": "negative", "minutes": -1})
    document_params = {**p, "request_id": "invoice-1", "matter_id": matter["id"], "kind": "invoice", "fee_ids": [fee["id"]], "due_on": date.today().isoformat()}
    doc = call("legal.document.create", **document_params)["documents"][0]
    assert doc["total_cents"] == 10000
    assert doc["snapshot"]["jurisdiction"] == "FR"
    assert doc["snapshot"]["issuer"]["siren"] == "123456789"
    assert doc["snapshot"]["payment_terms"]["recovery_indemnity_cents"] == 4000
    assert len(call("legal.document.create", **document_params)["documents"]) == 1
    fail("legal.document.create", **{**document_params, "request_id": "double-billing"})
    call("legal.client.save", **p, **{**client, "name": "Nom modifié"})
    assert call("legal.snapshot", **p)["documents"][0]["snapshot"]["client"]["name"] == "Client témoin"
    payment_params = {**p, "request_id": "payment-1", "document_id": doc["id"], "amount_cents": 3000, "paid_on": date.today().isoformat(), "reference": "Virement témoin"}
    state = call("legal.payment.add", **payment_params)
    assert state["documents"][0]["balance_cents"] == 7000
    assert len(call("legal.payment.add", **payment_params)["payments"]) == 1
    fail("legal.payment.add", **{**payment_params, "request_id": "overpayment", "amount_cents": 7001})
    second_fee = call("legal.fee.add", **{**p, "request_id": "fee-2", "matter_id": matter["id"], "description": "Audience", "kind": "fixed", "amount_cents": 5000, "tax_bps": 2000})["fees"][-1]
    second_invoice = call("legal.document.create", **{**p, "request_id": "invoice-2", "matter_id": matter["id"], "kind": "invoice", "fee_ids": [second_fee["id"]], "due_on": date.today().isoformat(), "purpose": "provision_expenses_fees"})["documents"][-1]
    allocation = {"project_id": pid, "request_id": "receipt-split-1", "amount_cents": 5000, "paid_on": date.today().isoformat(), "reference": "Virement regroupé", "allocations": [{"document_id": doc["id"], "amount_cents": 3000}, {"document_id": second_invoice["id"], "amount_cents": 2000}]}
    split_state = call("legal.payment.allocate", **allocation)
    assert len([payment for payment in split_state["payments"] if payment["reference"] == "Virement regroupé"]) == 2
    assert next(item for item in split_state["documents"] if item["id"] == second_invoice["id"])["snapshot"]["purpose"] == "provision_expenses_fees"
    assert len(call("legal.payment.allocate", **allocation)["payments"]) == 3
    fail("legal.payment.allocate", **{**allocation, "request_id": "bad-split", "amount_cents": 7000})
    third_fee = call("legal.fee.add", **{**p, "request_id": "fee-3", "matter_id": matter["id"], "description": "Consultation à annuler", "kind": "fixed", "amount_cents": 1000, "tax_bps": 2000})["fees"][-1]
    third_invoice = call("legal.document.create", **{**p, "request_id": "invoice-3", "matter_id": matter["id"], "kind": "invoice", "fee_ids": [third_fee["id"]], "due_on": date.today().isoformat()})["documents"][-1]
    credit_params = {"project_id": pid, "request_id": "credit-1", "document_id": third_invoice["id"], "reason": "Annulation du dossier"}
    credited = call("legal.document.credit", **credit_params)
    assert any(item["kind"] == "credit_note" and item["related_document_id"] == third_invoice["id"] for item in credited["documents"])
    assert next(item for item in credited["documents"] if item["id"] == third_invoice["id"])["cancelled"] is True
    assert len(call("legal.document.credit", **credit_params)["documents"]) == 4
    other_pid = call("projects.create", name="Autre projet", folders=[str(tmp_path / "other")])["project"]["id"]
    other_state = call("legal.snapshot", project_id=other_pid)
    assert other_state["firm_settings"]["siren"] == "123456789"
    assert other_state["firm_totals"]["invoiced_cents"] == 16000
    fail("legal.payment.add", **{**payment_params, "project_id": other_pid, "request_id": "foreign"})
    fail("legal.workspace.set", **p, domain="fiscal")
    state = call("legal.snapshot", **p)
    assert state["acts"][0]["body"] == "Dossier : {{dossier}}"
    assert len(state["payments"]) == 3 and len(state["documents"]) == 4
    assert state["firm_totals"]["fees_cents"] == 14333
    assert state["firm_totals"]["invoiced_cents"] == 16000
    assert state["firm_totals"]["paid_cents"] == 8000
    assert state["firm_totals"]["by_user"] == [{"user": "Avocate A", "fees_cents": 8333, "fee_count": 1}]
    assert state["firm_totals"]["by_matter"][0]["matter_id"] == matter["id"]
    # Every request reopened the real DB; deletion still observes the project FK boundary.
    call("projects.delete", id=pid)
    assert server._methods["legal.snapshot"](1, p)["error"]["code"] == 5062


def test_legal_rpc_scopes_two_profile_homes_a_b_a(monkeypatch, tmp_path):
    homes = {name: tmp_path / name for name in ("default", "legal-b")}
    for home in homes.values():
        home.mkdir()
    monkeypatch.setattr("hermes_cli.profiles.get_profile_dir", lambda name: homes[name])
    previous_home = server._hermes_home
    server._hermes_home = homes["default"]
    token = set_hermes_home_override(homes["default"])
    try:
        states = {}
        for profile, domain in (("default", "societes"), ("legal-b", "penal")):
            project = call("projects.create", profile=profile, name=domain, folders=[str(tmp_path / domain)])["project"]
            p = {"profile": profile, "project_id": project["id"]}
            call("legal.workspace.set", **p, domain=domain)
            call("legal.client.save", **p, name=profile)
            states[profile] = (p, call("legal.snapshot", **p))
        for profile in ("default", "legal-b", "default"):
            p, expected = states[profile]
            assert call("legal.snapshot", **p) == expected
        wrong = {**states["default"][0], "profile": "legal-b"}
        assert server._methods["legal.snapshot"](1, wrong)["error"]["code"] == 5062
        with pytest.raises(ValueError):
            call("legal.fee.add", **states["default"][0], request_id="decimal", matter_id="missing", description="bad", kind="fixed", amount_cents=1.5)
    finally:
        server._hermes_home = previous_home
        reset_hermes_home_override(token)


def test_legal_time_codes_subscriptions_and_linked_document_drafts(tmp_path):
    pid = call("projects.create", name="Cabinet temps", folders=[str(tmp_path)])['project']['id']
    p = {"project_id": pid}
    call("legal.workspace.set", **p, domain="social")
    call("legal.firm.settings.set", **p, legal_name="Cabinet Test", address="1 rue Test", siren="123456789",
         vat_number="FR00123456789", vat_regime="standard")
    client = call("legal.client.save", **p, name="Client", address="10 rue Test")["clients"][0]
    matter = call("legal.matter.save", **p, client_id=client["id"], title="Dossier", matter_type="Rupture du contrat")["matters"][0]
    code = call("legal.fee_code.save", **p, request_id="code-1", code="TEL", label="Appel", hourly_rate_cents=18000, fixed_amount_cents=2500, tax_bps=2000)["fee_codes"][0]
    call("legal.fee_code.save", **p, request_id="code-2", id=code["id"], code="TEL", label="Appel client", hourly_rate_cents=20000, fixed_amount_cents=2500, tax_bps=2000)
    assert call("legal.snapshot", **p)["fee_codes"][0]["hourly_rate_cents"] == 20000
    time_params = {**p, "request_id": "time-1", "matter_id": matter["id"], "description": "Appel au client", "kind": "time", "minutes": 30, "rate_cents": 20000, "tax_bps": 2000, "responsible_user": "Avocate A", "activity_date": date.today().isoformat(), "activity_type": "phone", "billing_code": "TEL", "billable": True}
    fee = call("legal.fee.add", **time_params)["fees"][0]
    assert (fee["net_cents"], fee["activity_type"], fee["billing_code"], fee["responsible_user"]) == (10000, "phone", "TEL", "Avocate A")
    unbillable = call("legal.fee.add", **{**time_params, "request_id": "time-nonbillable", "description": "Suivi interne", "billable": False})["fees"][-1]
    assert unbillable["billable"] is False
    assert call("legal.snapshot", **p)["firm_totals"]["fees_cents"] == 10000
    fail("legal.document.create", **{**p, "request_id": "nonbillable-invoice", "matter_id": matter["id"], "kind": "invoice", "fee_ids": [unbillable["id"]], "due_on": date.today().isoformat()})
    fail("legal.fee.add", **{**time_params, "request_id": "future-time", "activity_date": (date.today() + timedelta(days=1)).isoformat()})
    form = call("legal.practice_document.create", **p, request_id="form-1", matter_id=matter["id"], template_id="document_communication", fee_ids=[fee["id"]])
    assert form["practice_documents"][0]["fee_ids"] == [fee["id"]]
    assert "Client : Client" in form["practice_documents"][0]["body"]
    today = date.today().isoformat()
    subscription_params = {**p, "request_id": "sub-1", "matter_id": matter["id"], "label": "Conseil récurrent", "amount_cents": 50000, "tax_bps": 2000, "cadence": "annual", "starts_on": today, "next_invoice_on": today}
    sub = call("legal.subscription.save", **subscription_params)["subscriptions"][0]
    invoice_params = {**p, "request_id": "sub-invoice-1", "subscription_id": sub["id"]}
    invoiced = call("legal.subscription.invoice", **invoice_params)
    assert len(invoiced["documents"]) == 1
    assert invoiced["documents"][0]["purpose"] == "subscription"
    assert invoiced["documents"][0]["total_cents"] == 60000
    assert invoiced["subscriptions"][0]["next_invoice_on"][:4] == str(date.today().year + 1)
    assert len(call("legal.subscription.invoice", **invoice_params)["documents"]) == 1
    assert len(call("legal.snapshot", **p)["fees"]) == 3


def test_company_matter_profile_is_editable_and_flows_into_drafts(tmp_path):
    pid = call("projects.create", name="Cabinet sociétés", folders=[str(tmp_path)])['project']['id']
    p = {"project_id": pid}
    call("legal.workspace.set", **p, domain="societes")
    call("legal.firm.settings.set", **p, legal_name="Cabinet Test", address="1 rue Test", siren="123456789",
         vat_number="FR00123456789", vat_regime="standard")
    client = call("legal.client.save", **p, name="Holding cliente", address="10 rue Client", customer_type="professional", siren="987654321")["clients"][0]
    profile = {
        "company_details": {"registered_name": "Société Exemple SAS", "legal_form": "SAS", "siren": "111222333", "registered_office": "2 rue des Sociétés, Lyon"},
        "capital_rights": {"capital": "10 000 EUR"},
        "associates": {"members": "Alice Exemple — 60 actions\nBob Exemple — 40 actions"},
        "management": {"president": "Alice Exemple"},
        "tax": {"tax_regime": "IS"},
    }
    matter = call("legal.matter.save", **p, client_id=client["id"], title="Vie sociale", matter_type="Vie sociale", reference="SOC-42", company_profile=profile)["matters"][0]
    assert matter["company_profile"] == profile
    profile_sections = {item["id"] for item in call("legal.snapshot", **p)["company_profile_schema"]}
    assert {"matter_organization", "company_details", "capital_rights", "associates", "management", "tax"} <= profile_sections
    closed = call("legal.matter.save", **p, **{**matter, "status": "closed"})["matters"][0]
    assert closed["company_profile"] == profile
    updated_profile = call("legal.matter.save", **p, id=matter["id"], client_id=client["id"], title=matter["title"],
                           matter_type=matter["matter_type"], reference=matter["reference"], status="closed",
                           matter_profile={"management": {"president": "Alice Exemple — mise à jour"}})["matters"][0]
    assert updated_profile["matter_profile"]["management"]["president"] == "Alice Exemple — mise à jour"
    assert updated_profile["matter_profile"]["company_details"] == profile["company_details"]
    fee = call("legal.fee.add", **p, request_id="company-fee-1", matter_id=matter["id"], description="Conseil juridique", kind="fixed", amount_cents=10000, tax_bps=2000)["fees"][0]
    form = call("legal.practice_document.create", **p, request_id="company-draft-1", matter_id=matter["id"], template_id="end_of_mission")["practice_documents"][0]
    assert "Informations société du dossier" in form["body"]
    assert "Société Exemple SAS" in form["body"] and "Alice Exemple" in form["body"]
    invoice = call("legal.document.create", **p, request_id="company-invoice-1", matter_id=matter["id"], kind="invoice", fee_ids=[fee["id"]], due_on=date.today().isoformat())["documents"][0]
    assert invoice["snapshot"]["matter"]["company_profile"] == profile
    assert "Société concernée par le dossier" in invoice["rendered_document"]
    assert "SIREN : 111222333" in invoice["rendered_document"]
    assert "SIREN client : 987654321" in invoice["rendered_document"]


def test_company_profile_rejects_non_text_and_excessive_content(tmp_path):
    pid = call("projects.create", name="Cabinet validité", folders=[str(tmp_path)])['project']['id']
    p = {"project_id": pid}
    call("legal.workspace.set", **p, domain="societes")
    client = call("legal.client.save", **p, name="Client")["clients"][0]
    params = {**p, "client_id": client["id"], "title": "Dossier", "matter_type": "Constitution"}
    fail("legal.matter.save", **params, company_profile={"company_details": {"siren": 123456789}})
    fail("legal.matter.save", **params, company_profile={"company_details": {"siren": "x" * 20_001}})


def test_real_estate_profile_matches_dossier_menu_and_flows_to_document(tmp_path):
    pid = call("projects.create", name="Cabinet baux", folders=[str(tmp_path)])['project']['id']
    p = {"project_id": pid}
    call("legal.workspace.set", **p, domain="immobilier")
    client = call("legal.client.save", **p, name="Société locataire")['clients'][0]
    profile = {
        "matter_organization": {"summary": "Renouvellement du bail commercial", "cote": "BAIL-2026-01"},
        "parties": {"tenant": "Société locataire — 12 rue Exemple, Lyon"},
        "guarantee": {"guarantor": "Mme Exemple", "guarantee_type": "Caution solidaire"},
        "lease_transfer": {"assignor": "Ancien preneur", "assignee": "Nouveau preneur", "transfer_date": "À définir"},
        "lease": {"lease_type": "Bail commercial", "landlord": "SCI Exemple", "rent": "2 000 EUR / mois"},
        "premises": {"address": "12 rue Exemple, Lyon", "surface": "85 m²"},
        "notice": {"notice_from": "Bailleur", "effective_date": "30/09/2026"},
        "real_property": {"identification": "Appartement lot 12", "title": "Acte du 4 mai 2018", "cadastre": "Section AB parcelle 42", "diagnostics": "DPE à jour", "easements": "Servitude de passage", "mortgages": "Hypothèque levée"},
        "transactions": {"precontract": "Compromis signé", "conditions": "Prêt avant le 30/11", "financing": "Prêt bancaire", "sale_deed": "Signature prévue", "vefa": "Sans objet"},
        "urbanism": {"building_permit": "PC-2026-01", "prior_declaration": "Sans objet", "planning_documents": "PLU zone U", "appeals": "Aucun recours connu", "demolition": "Sans objet"},
        "condominium": {"bylaws": "Règlement 2018", "meetings": "AG du 15/06/2026", "property_manager": "Syndic Exemple", "charges": "900 EUR / trimestre", "works": "Ravalement voté"},
        "lease_types": {"residential_lease": "Sans objet", "commercial_lease": "Bail 3/6/9", "professional_lease": "Sans objet", "leave_notice": "Préavis à vérifier", "unpaid_rent": "Aucun impayé déclaré"},
        "billable_clients": {"third_parties": "Société locataire — facturation"},
    }
    matter = call("legal.matter.save", **p, client_id=client["id"], title="Bail commercial", matter_type="Bail commercial", matter_profile=profile)["matters"][0]
    assert matter["matter_profile"] == profile
    section_ids = {section["id"] for section in call("legal.snapshot", **p)["matter_profile_schema"]}
    assert {"matter_organization", "parties", "guarantee", "lease_transfer", "lease", "premises", "notice", "real_property", "transactions", "urbanism", "condominium", "lease_types", "billable_clients"} <= section_ids
    assert {"correspondence", "expenses", "misc_documents"} <= {field["id"] for field in next(s for s in call("legal.snapshot", **p)["matter_profile_schema"] if s["id"] == "matter_organization")["fields"]}
    draft = call("legal.practice_document.create", **p, request_id="lease-draft-1", matter_id=matter["id"], template_id="quick_letter")["practice_documents"][0]
    assert "Preneur" in draft["body"] and "Caution" in draft["body"] and "Cession de droit au bail" in draft["body"]
    assert "Locaux" in draft["body"] and "Congé" in draft["body"] and "Société locataire" in draft["body"]
    assert "Bien immobilier" in draft["body"] and "Compromis signé" in draft["body"]
    assert "Syndic Exemple" in draft["body"] and "Bail 3/6/9" in draft["body"]


def test_agricultural_profile_matches_exploitation_conventions_and_aid_menus(tmp_path):
    pid = call("projects.create", name="Cabinet agricole", folders=[str(tmp_path)])['project']['id']
    p = {"project_id": pid}
    call("legal.workspace.set", **p, domain="agricole")
    client = call("legal.client.save", **p, name="Ferme Exemple")['clients'][0]
    profile = {
        "parties": {"operator": "Ferme Exemple", "landlord": "Indivision Exemple", "company": "EARL Exemple"},
        "farm_operations": {"operations": "Exploitation des Prés", "parcels": "Parcelles AB 12, AB 13", "crop_rotation": "Blé / colza", "farm_buildings": "Grange cadastrée AB 90"},
        "conventions": {"availability_agreements": "Convention de mise à disposition 2024", "rural_leases": "Bail rural signé en 2020", "sharefarming": "Fermage annuel 1 200 EUR", "commodat": "Prêt à usage de matériel", "company_availability": "Mise à disposition à l’EARL"},
        "msa": {"msa_statements": "Relevé MSA T2", "social_contributions": "Cotisations 2026", "msa_declarations": "Déclaration annuelle déposée"},
        "pac_aids": {"pac_declaration": "Déclaration PAC 2026", "payment_entitlements": "DPB associés aux parcelles", "coupled_aid": "Aide protéagineux", "maec": "MAEC engagée jusqu’en 2028"},
        "installation_transmission": {"installation": "Dossier d’installation ouvert en 2020", "structural_control": "Autorisation obtenue", "transmission": "Transmission familiale envisagée", "safer": "Déclaration SAFER à vérifier"},
        "environment": {"icpe_livestock": "ICPE enregistrée", "nitrates_directive": "Plan d’action en cours", "water_management": "Prélèvement autorisé", "hedges_and_coppice": "Haies protégées", "environmental_permits": "Zone vulnérable nitrates", "environmental_proceedings": "Aucune procédure déclarée"},
        "rural_contention": {"dispute": "Contestation de fermage", "parties": "EARL Exemple / bailleur", "deadlines": "Réponse avant le 15/12/2026", "evidence": "Bail et quittances"},
    }
    matter = call("legal.matter.save", **p, client_id=client["id"], title="Exploitation des Prés", matter_type="Bail rural", matter_profile=profile)["matters"][0]
    assert matter["matter_profile"] == profile
    schema = call("legal.snapshot", **p)["matter_profile_schema"]
    section_ids = {section["id"] for section in schema}
    assert {"farm_operations", "conventions", "msa", "pac_aids", "installation_transmission", "environment", "rural_contention", "billable_clients"} <= section_ids
    draft = call("legal.practice_document.create", **p, request_id="farm-draft-1", matter_id=matter["id"], template_id="quick_letter")["practice_documents"][0]
    assert "Parcelles AB 12, AB 13" in draft["body"]
    assert "Convention de mise à disposition 2024" in draft["body"]
    assert "Déclaration PAC 2026" in draft["body"] and "Contestation de fermage" in draft["body"]
    assert "Dossier d’installation ouvert en 2020" in draft["body"]
    assert "ICPE enregistrée" in draft["body"] and "Haies protégées" in draft["body"]


def test_contentious_and_transport_menus_flow_into_draft_context(tmp_path):
    pid = call("projects.create", name="Cabinet contentieux et transport", folders=[str(tmp_path)])['project']['id']
    p = {"project_id": pid}
    client = call("legal.client.save", **p, name="Client Exemple")['clients'][0]
    examples = {
        "contentieux-judiciaire": {
            "profile": {
                "procedure_tracking": {"parties_and_counsel": "Demandeur / Cabinet Exemple", "jurisdiction": "TJ de Lyon", "procedural_calendar": "Mise en état le 12/12/2026", "hearings": "Audience le 15/01/2027", "deadlines": "Conclusions avant le 30/11/2026"},
                "case_pieces": {"claimant_pieces": "Pièce demandeur 1", "defendant_pieces": "Pièce défendeur 2", "pleadings": "Conclusions récapitulatives", "expert_reports": "Rapport d’expertise"},
                "decision": {"judgment": "Jugement du 01/02/2027", "appeal": "Appel à examiner", "execution": "Exécution provisoire"},
            },
            "sections": {"procedure_tracking", "case_pieces", "decision"},
            "values": ("TJ de Lyon", "Pièce demandeur 1", "Jugement du 01/02/2027"),
        },
        "transport": {
            "profile": {
                "transport_contracts": {"cmr": "CMR 2026-100", "bill_of_lading": "B/L 55", "air_waybill": "LTA 77", "charter": "Affrètement du 10/10", "freight_forwarding": "Commission Exemple", "subcontracting": "Sous-traitant ABC"},
                "responsibilities": {"damage_and_loss": "Avarie palettes 2-4", "delivery_delays": "Retard de 48 h", "liability_limits": "Convention applicable à vérifier", "transport_insurance": "Police assureur XYZ", "recourse_subrogation": "Recours notifié"},
                "regulation": {"licenses": "Licence communautaire", "professional_capacity": "Capacité attestée", "driving_rest_time": "Chronotachygraphe joint", "dangerous_goods": "ADR classe 3", "cabotage": "Opération contrôlée"},
                "transport_litigation": {"expertises": "Expertise contradictoire", "arbitration": "Clause CCI", "limitation_period": "Prescription au 31/12/2026", "compensation": "Indemnisation demandée"},
            },
            "sections": {"transport_contracts", "responsibilities", "regulation", "transport_litigation"},
            "values": ("CMR 2026-100", "Avarie palettes 2-4", "Licence communautaire", "Indemnisation demandée"),
        },
    }
    for index, (domain, example) in enumerate(examples.items()):
        call("legal.workspace.set", **p, domain=domain)
        schema = call("legal.snapshot", **p)["matter_profile_schema"]
        assert example["sections"] <= {section["id"] for section in schema}
        matter = call("legal.matter.save", **p, client_id=client["id"], title=f"Dossier {domain}",
                      matter_type=call("legal.snapshot", **p)["matter_types"][0], matter_profile=example["profile"])["matters"][-1]
        draft = call("legal.practice_document.create", **p, request_id=f"transport-court-draft-{index}",
                     matter_id=matter["id"], template_id="quick_letter")["practice_documents"][-1]
        assert all(value in draft["body"] for value in example["values"])


def test_legal_catalog_contains_requested_practice_areas_and_presets(tmp_path):
    expected = [
        "Droit Pénal et Procédure", "Contentieux Judiciaire", "Droit des Affaires",
        "Droit des Sociétés", "Droit Social / Travail", "Droit Fiscal", "Droit Notarié",
        "Baux & Contrats", "Droit du Sport", "Droit Agricole", "Droit du Transport",
        "Droit de Douane", "Droit Médical", "Recouvrement", "Droit Patrimonial et Famille",
        "Droit des Personnes Protégées", "Droit Civil", "Droit NTIC & Propriété Intellectuelle",
        "Droit de l'E-Sport", "Droit Aérien",
    ]
    pid = call("projects.create", name="Cabinet multi-domaines", folders=[str(tmp_path)])["project"]["id"]
    domains = call("legal.snapshot", project_id=pid)["domains"]
    assert [domain["label"] for domain in domains[:20]] == expected
    assert domains[20]["id"] == "administratif"  # Preserve existing workspace IDs.
    for domain in domains:
        assert domain["matter_types"] and domain["act_types"]
        state = call("legal.workspace.set", project_id=pid, domain=domain["id"])
        assert state["domain"] == domain["id"]
        assert state["matter_types"] == domain["matter_types"]
        schema = call("legal.snapshot", project_id=pid)["matter_profile_schema"]
        assert len(schema) >= 3
        assert {section["id"] for section in schema} >= {"matter_organization", "evidence_register", "document_generator", "billable_clients"}


def test_tax_family_and_social_profiles_follow_supplied_dossier_menus(tmp_path):
    pid = call("projects.create", name="Cabinet exemples de dossiers", folders=[str(tmp_path)])['project']['id']
    p = {"project_id": pid}
    client = call("legal.client.save", **p, name="Client Exemple")['clients'][0]
    examples = {
        "fiscal": {
            "sections": {"tax_dashboard", "tax_declarations", "tax_packages", "tax_integration", "tax_controls", "tax_litigation", "tax_ruling"},
            "profile": {
                "tax_dashboard": {"created_on": "15/10/2026", "imported_documents": "12", "tax_regime": "IS", "fiscal_stakes": "45 000 EUR", "fiscal_year": "2025"},
                "tax_declarations": {"declaration_type": "IS", "tax_year": "2025", "filing_status": "À préparer"},
                "tax_packages": {"package_type": "Liasse IS", "fiscal_year": "2025"},
                "tax_integration": {"group_parent": "Holding Exemple", "group_members": "Filiale Exemple"},
                "tax_controls": {"control_type": "Vérification de comptabilité", "reply_deadline": "30/11/2026"},
                "tax_litigation": {"decision_contested": "Proposition de rectification"},
                "tax_ruling": {"question": "Régime applicable à l’opération"},
            },
            "expected_text": ("45 000 EUR", "Liasse IS", "Vérification de comptabilité"),
        },
        "patrimonial-famille": {
            "sections": {"civil_status", "property_liquidation", "children_authority", "family_procedure", "family_finances", "family_tools"},
            "profile": {
                "civil_status": {"spouse_identity": "Alice et Benoît Exemple", "marriage_contract": "Séparation de biens"},
                "property_liquidation": {"community_assets": "Maison de Lyon", "liquidation_proposal": "Vente puis partage"},
                "children_authority": {"children_identity": "Camille, 8 ans", "residence": "Alternée", "parental_authority": "Conjointe"},
                "family_procedure": {"proceedings": "Divorce par consentement mutuel"},
                "family_finances": {"income_by_party": "Revenus mensuels des deux parties"},
                "family_tools": {"missing_documents": "Relevés bancaires"},
            },
            "expected_text": ("Alice et Benoît Exemple", "Maison de Lyon", "Camille, 8 ans"),
        },
        "social": {
            "sections": {"employees", "social_information", "representative_institutions", "urssaf", "labor_inspection", "contracts", "litigation"},
            "profile": {
                "employees": {"employee_list": "Camille Exemple", "employee_count": "42"},
                "social_information": {"collective_agreement_details": "IDCC 1486"},
                "representative_institutions": {"social_economic_committee": "CSE élu le 10/01/2026", "union_representatives": "Sam Exemple"},
                "urssaf": {"urssaf_office": "URSSAF Rhône-Alpes", "deadline": "20/11/2026"},
                "labor_inspection": {"inspection_office": "Inspection du travail de Lyon"},
                "contracts": {"contract_types": "CDI et avenant"},
                "litigation": {"court": "Conseil de prud’hommes de Lyon"},
            },
            "expected_text": ("Camille Exemple", "IDCC 1486", "URSSAF Rhône-Alpes"),
        },
    }
    for index, (domain, example) in enumerate(examples.items()):
        call("legal.workspace.set", **p, domain=domain)
        snapshot = call("legal.snapshot", **p)
        assert example["sections"] <= {section["id"] for section in snapshot["matter_profile_schema"]}
        matter = call("legal.matter.save", **p, client_id=client["id"], title=f"Dossier {domain}",
                      matter_type=snapshot["matter_types"][0], matter_profile=example["profile"])["matters"][-1]
        draft = call("legal.practice_document.create", **p, request_id=f"menu-example-{index}",
                     matter_id=matter["id"], template_id="quick_letter")["practice_documents"][-1]
        assert all(text in draft["body"] for text in example["expected_text"])

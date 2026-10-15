"""Real project/RPC/SQLite boundaries: billing arithmetic, retry safety and profile ownership."""
from datetime import date

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

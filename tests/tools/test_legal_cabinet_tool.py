from __future__ import annotations

import json
from datetime import date

from hermes_cli import projects_db as pdb
from tools import legal_cabinet
from tools.registry import registry


def test_chat_tool_manages_project_workspace_and_invoice_draft(monkeypatch, tmp_path):
    db_path = tmp_path / "projects.db"
    original_connect = pdb.connect_closing
    monkeypatch.setattr(pdb, "connect_closing", lambda: original_connect(db_path=db_path))
    with original_connect(db_path=db_path) as conn:
        project_id = pdb.create_project(conn, name="Cabinet social", folders=[str(tmp_path)])
        pdb.set_active(conn, project_id)

    result = json.loads(legal_cabinet.legal_cabinet("workspace.set", domain="social"))
    assert result["success"] is True
    assert result["data"]["matter_types"]

    result = json.loads(legal_cabinet.legal_cabinet(
        "firm.settings.set", legal_name="Cabinet Test", address="1 rue Test, Paris",
        siren="123456789", vat_number="FR00123456789", vat_regime="standard",
    ))
    assert result["success"] is True
    client = legal_cabinet.legal_cabinet(
        "client.save", name="Client test", address="10 rue Test", email="client@example.test"
    )
    client = json.loads(client)["data"]["clients"][0]
    matter = json.loads(legal_cabinet.legal_cabinet(
        "matter.save", client_id=client["id"], title="Dossier social",
        matter_type="Rupture du contrat", reference="SOC-01",
    ))["data"]["matters"][0]
    fee = json.loads(legal_cabinet.legal_cabinet(
        "fee.add", request_id="fee-chat-1", matter_id=matter["id"],
        description="Consultation", kind="fixed", amount_cents=10000, tax_bps=2000,
    ))["data"]["fees"][0]
    invoice = json.loads(legal_cabinet.legal_cabinet(
        "document.create", request_id="invoice-chat-1", matter_id=matter["id"],
        kind="invoice", fee_ids=[fee["id"]], due_on=date.today().isoformat(),
    ))

    assert invoice["success"] is True
    assert invoice["data"]["documents"][0]["total_cents"] == 12000
    assert "Détail des prestations" in invoice["data"]["rendered_document"]
    assert "BROUILLON INTERNE — NON ÉMIS" in invoice["data"]["rendered_document"]
    assert registry.get_entry("legal_cabinet").toolset == "project"


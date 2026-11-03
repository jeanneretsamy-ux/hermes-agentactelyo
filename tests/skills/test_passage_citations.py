"""Real source spans bind every citation to the correct snapshot and location."""
import importlib.util
from pathlib import Path

import pytest

script = Path(__file__).resolve().parents[2] / "skills/research/grounded-citations/scripts/passages.py"
spec = importlib.util.spec_from_file_location("research_passages", script)
passages = importlib.util.module_from_spec(spec)
spec.loader.exec_module(passages)


@pytest.mark.parametrize("field,value", [("source_id", "2"), ("page", 99), ("start", 1),
                                         ("quote", "Le dépôt est de 9999 euros.")])
def test_selection_cannot_move_a_quote_to_another_file_or_location(field, value):
    sources = {"1": {"url": "file:///alpha.docx", "page": 2, "text": "Le dépôt est de 4817 euros."},
               "2": {"url": "file:///beta.docx", "page": 2, "text": "Le dépôt est de 4817 euros."}}
    catalog = passages.build_catalog(sources)
    assert len(catalog) == len(set(catalog))
    assert set(catalog) == set(passages.build_catalog(dict(reversed(list(sources.items())))))
    pid = next(pid for pid, item in catalog.items() if item["source_id"] == "1")
    claims = passages.assemble_claims([{"id": "c", "text": "4817 euros", "passage_ids": [pid]}], catalog)
    evidence = claims[0]["evidence"][0]
    assert sources["1"]["text"][evidence["start"]:evidence["end"]] == evidence["quote"]
    evidence[field] = value
    assert passages.verify_bindings(claims, sources)
    with pytest.raises(ValueError, match="unknown"):
        passages.assemble_claims([{"id": "c", "text": "4817 euros", "passage_ids": ["invented"]}], catalog)


@pytest.mark.parametrize("name,text", [
    ("factures.csv", 'Dossier;Facture;TTC\nALPHA;FA-042;3000\nBETA;FB-042;9000\n'),
    ("factures.md", '| Dossier | Facture | TTC |\n|---|---|---|\n| ALPHA | FA-042 | 3000 |\n| BETA | FB-042 | 9000 |\n'),
    ("factures.csv", 'Dossier;Description;TTC\nALPHA;"Prestation\ncomplémentaire";3000\n'),
])
def test_table_selection_preserves_headers_rows_and_literal_citations(name, text):
    sources = {"1": {"url": "file:///"+name, "text": text}}
    catalog = passages.build_catalog(sources)
    pid = next(pid for pid, row in catalog.items() if row["table"]["cells"][-1]["value"] == "3000")
    selected = passages.assemble_claims([{"id": "c", "text": "Le TTC est de 3000 euros.", "passage_ids": [pid]}], catalog)
    quote = selected[0]["evidence"][0]
    assert quote["table"]["cells"][0] == {"column": 1, "header": "Dossier", "value": "ALPHA"}
    assert text[quote["start"]:quote["end"]] == quote["quote"]
    assert passages.verify_bindings(selected, sources) == []
    rendered = passages.render_report({"status": "approved", "claims": selected})
    assert "page non renseignée" in rendered
    assert "Colonnes" in rendered and "ALPHA" in rendered and "3000" in rendered
    blocked = passages.render_report({"status": "research_again", "claims": selected})
    assert "3000" not in blocked

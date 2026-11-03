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
    limited = passages.select_context(catalog, "ALPHA dépôt", 1)
    assert pid in limited
    other = next(pid for pid, item in catalog.items() if item["source_id"] == "2")
    with pytest.raises(ValueError, match="unknown"):
        passages.assemble_claims([{"id": "c", "text": "4817 euros", "passage_ids": [other]}], limited)
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
    ("factures.csv", '| Dossier | Facture | TTC |\n| --- | --- | --- |\n| ALPHA | FA-042 | 3000 |\n'),
    ("factures.md", '| Dossier | Description | TTC |\n|---|---|---|\n| ALPHA | A \\| B | 3000 |\n'),
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


def test_table_amount_check_rejects_ht_ttc_and_other_invoice_confusion():
    source={"1":{"url":"file:///factures.csv","text":"Dossier;Facture;HT;TTC\nALPHA;FA-042;2500;3000\nBETA;FB-041;9000;10800\n"}}
    catalog=passages.build_catalog(source)
    alpha=next(pid for pid,row in catalog.items() if row['table']['cells'][0]['value']=='ALPHA')
    beta=next(pid for pid,row in catalog.items() if row['table']['cells'][0]['value']=='BETA')
    question="Quel est le TTC de FA-042 du dossier ALPHA ?"
    for text,pid in [("Le TTC de FA-042 est de 2500 euros.",alpha),("Le TTC est de 10800 euros.",beta)]:
        claims=passages.assemble_claims([{"id":"c","text":text,"passage_ids":[pid]}],catalog)
        assert passages.verify_table_amounts(question,claims,catalog)
    good=passages.assemble_claims([{"id":"c","text":"Le TTC est de 3 000 euros.","passage_ids":[alpha]}],catalog)
    assert passages.verify_table_amounts(question,good,catalog)==[]
    schedule={"1":{"url":"file:///schedule.csv","text":"Dossier;Échéance;Montant\nGAMMA;15/01/2027;1350\nGAMMA;15/02/2027;2460\nDELTA;15/02/2027;9990\n"}}
    schedule_catalog=passages.build_catalog(schedule)
    january=next(pid for pid,row in schedule_catalog.items() if row['table']['cells'][-1]['value']=='1350')
    wrong=passages.assemble_claims([{"id":"c","text":"Le montant dû est de 1350 euros.","passage_ids":[january]}],schedule_catalog)
    assert passages.verify_table_amounts("Quel montant doit GAMMA le 15 février 2027 ?",wrong,schedule_catalog)

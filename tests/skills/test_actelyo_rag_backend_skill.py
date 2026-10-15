from pathlib import Path


def test_actelyo_rag_skill_routes_legal_drafts_through_indexed_examples():
    root = Path(__file__).resolve().parents[2]
    skill = (root / "skills/legal/actelyo-rag-backend/SKILL.md").read_text(encoding="utf-8")
    cabinet = (root / "tools/legal_cabinet.py").read_text(encoding="utf-8")

    assert "Legal drafting and billing workflow" in skill
    assert "actelyo_rag_vector_search" in skill
    assert 'legal_cabinet(action="snapshot")' in skill
    assert "never copy facts from another client's dossier" in skill
    assert "untrusted source material" in skill
    assert "consult the Actelyo RAG skill" in cabinet

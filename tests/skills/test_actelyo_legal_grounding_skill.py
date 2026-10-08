from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "legal" / "actelyo-legal-grounding" / "SKILL.md"


def test_grounding_skill_has_source_guardrails() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "name: actelyo-legal-grounding" in text
    assert "openlegi-official-sources" in text
    assert "legal-data-hunter" in text
    assert "fabricate a citation" in text
    assert "## Verification" in text

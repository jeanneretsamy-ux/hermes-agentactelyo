from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "productivity" / "actelyo-legal-work-product" / "SKILL.md"


def test_work_product_stays_draft_only_without_connector() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "name: actelyo-legal-work-product" in text
    assert "does not send mail" in text
    assert "explicit action-time approval" in text
    assert "idempotency key" in text
    assert "## Verification" in text

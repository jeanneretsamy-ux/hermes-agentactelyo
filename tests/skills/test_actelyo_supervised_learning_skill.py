from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "legal" / "actelyo-supervised-learning" / "SKILL.md"
SCHEMA = ROOT / "skills" / "legal" / "actelyo-supervised-learning" / "references" / "feedback-schema.md"


def test_supervised_learning_requires_human_review() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert "name: actelyo-supervised-learning" in text
    assert "human approval" in text
    assert "Never let an automatic review approve its own patch." in text
    assert "pending_review" in text
    assert SCHEMA.is_file()

"""Regression checks for the French accounting and tax workflow skill."""
import re
from pathlib import Path

import hermes_yaml as yaml


REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "optional-skills/finance/france-accounting-tax/SKILL.md"


def test_skill_metadata_and_referenced_skills():
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    match = re.search(r"\n---\s*\n", text[4:])
    assert match
    frontmatter = yaml.safe_load(text[4 : match.start() + 4])
    assert frontmatter["name"] == SKILL.parent.name
    assert len(frontmatter["description"]) <= 60
    assert frontmatter["description"].endswith(".")
    assert set(frontmatter["metadata"]["hermes"]["related_skills"]) <= {
        path.parent.name
        for path in list((REPO / "skills").glob("**/SKILL.md"))
        + list((REPO / "optional-skills").glob("**/SKILL.md"))
    }


def test_workflows_cover_requested_tasks_and_restrict_external_actions():
    text = SKILL.read_text(encoding="utf-8").lower()
    for topic in (
        "rapprochement bancaire",
        "fec",
        "2561",
        "2777-sd",
        "2042",
        "2044",
        "2759-sd",
        "draft",
        "not filed",
    ):
        assert topic in text
    assert "never submits declarations or payments" in text
    assert "never initiate either" in text
    assert "do not create journal entries automatically" in text

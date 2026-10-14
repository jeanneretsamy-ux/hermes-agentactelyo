"""Regression checks for the French accounting and tax workflow skill."""
import re
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]
SKILL = REPO / "optional-skills/finance/france-accounting-tax/SKILL.md"


def test_skill_metadata_and_referenced_skills():
    text = SKILL.read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    assert match, "SKILL.md must start with valid frontmatter delimiters"
    frontmatter = match.group(1)
    name = re.search(r"^name: ([\w-]+)$", frontmatter, re.M)
    description = re.search(r'^description: "?(.*?)"?$', frontmatter, re.M)
    related = re.search(r"^    related_skills: \[(.*?)\]$", frontmatter, re.M)
    assert name and name.group(1) == SKILL.parent.name
    assert description and len(description.group(1)) <= 60
    assert description.group(1).endswith(".")
    assert related
    related_names = {item.strip() for item in related.group(1).split(",")}
    assert related_names <= {
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


if __name__ == "__main__":
    test_skill_metadata_and_referenced_skills()
    test_workflows_cover_requested_tasks_and_restrict_external_actions()
    print("French accounting and tax skill tests passed.")

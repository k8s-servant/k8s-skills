"""The README matches the skills: the verification table and the skill and scenario counts."""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
HEADING = "## How each skill is verified"


def readme_rows() -> dict[str, tuple[str, list[str]]]:
    """Rows of the table under HEADING: skill -> (verified with, scenario names)."""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    assert HEADING in text, f"README.md has no '{HEADING}' section"
    section = text.split(HEADING, 1)[1].split("\n## ", 1)[0]
    rows = {}
    for line in section.splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) == 3 and cells[0].startswith("`k8s-"):
            rows[cells[0].strip("`")] = (cells[1], re.findall(r"`([^`]+)`", cells[2]))
    return rows


def skill_facts() -> dict[str, tuple[str, list[str]]]:
    """Each skill's verified-with and its scenario folders under tests/."""
    facts = {}
    for skill_md in sorted((ROOT / "skills").glob("*/SKILL.md")):
        name = skill_md.parent.name
        front = yaml.safe_load(skill_md.read_text(encoding="utf-8").split("---")[1])
        cases = sorted(p.name for p in (ROOT / "tests" / name).iterdir() if p.is_dir())
        facts[name] = (front["metadata"]["verified-with"], cases)
    return facts


def test_readme_lists_every_skill_with_its_versions_and_scenarios():
    rows = readme_rows()
    for name, (versions, cases) in skill_facts().items():
        assert name in rows, f"{name} is missing from the README verification table"
        assert rows[name] == (versions, cases), name
    assert set(rows) == set(skill_facts())


def test_readme_counts_match_skills_and_scenarios():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    found = re.search(r"\*\*(\d+) skills, (\d+) scenarios\.\*\*", text)
    assert found, "README.md has no '**N skills, M scenarios.**' line"
    facts = skill_facts()
    scenarios = sum(len(cases) for _, cases in facts.values())
    assert (int(found[1]), int(found[2])) == (len(facts), scenarios)


def test_readme_skill_badge_matches_skills():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    found = re.search(r"https://img\.shields\.io/badge/skills-(\d+)-", text)
    assert found, "README.md has no skills count badge"
    assert int(found[1]) == len(skill_facts())

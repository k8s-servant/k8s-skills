"""Tests for the structure check: sections, Sources link, relative links, references."""

from pathlib import Path

from tools.skillcheck.structure import check_structure

FRONTMATTER = "---\nname: k8s-demo-skill\ndescription: Use when testing.\n---\n"
SECTIONS = ["When to use", "Investigate", "Read the results", "Proposed fix", "Sources"]


def body(sections: list[str] = SECTIONS, extra: str = "", sources: str = "") -> str:
    """Build a SKILL.md body with the given H2 sections."""
    out = ""
    for title in sections:
        out += f"## {title}\n\ntext\n\n"
        if title == "Sources":
            out += (sources or "- [Docs](https://example.com/docs)\n") + "\n"
    return out + extra


def make(root: Path, text: str, refs: dict[str, str] | None = None) -> Path:
    """Create skills/k8s-demo-skill with a SKILL.md and optional references."""
    skill_dir = root / "skills" / "k8s-demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(FRONTMATTER + text, encoding="utf-8")
    for name, content in (refs or {}).items():
        (skill_dir / "references").mkdir(exist_ok=True)
        (skill_dir / "references" / name).write_text(content, encoding="utf-8")
    return skill_dir


def messages(findings: list) -> list[str]:
    return [f.message for f in findings]


def test_valid_skill_passes(tmp_path):
    assert check_structure(make(tmp_path, body())) == []


def test_sections_in_order(tmp_path):
    wrong = ["When to use", "Read the results", "Investigate", "Proposed fix", "Sources"]
    found = check_structure(make(tmp_path, body(wrong)))
    assert messages(found) == [
        "sections must be: When to use, Investigate, Read the results, Proposed fix, Sources"
    ]


def test_missing_section_is_a_finding(tmp_path):
    found = check_structure(make(tmp_path, body(SECTIONS[:-1])))
    assert any("sections must be" in m for m in messages(found))


def test_missing_sources_link(tmp_path):
    found = check_structure(make(tmp_path, body(sources="- no link here\n")))
    assert "Sources must contain at least one https:// link" in messages(found)


def test_http_link_does_not_count_as_source(tmp_path):
    found = check_structure(make(tmp_path, body(sources="- [x](http://example.com)\n")))
    assert "Sources must contain at least one https:// link" in messages(found)


def test_broken_relative_link(tmp_path):
    found = check_structure(make(tmp_path, body(extra="See [x](references/gone.md).\n")))
    assert "broken relative link: references/gone.md" in messages(found)


def test_links_ignored_or_fragment_stripped(tmp_path):
    extra = "[a](#anchor) [b](mailto:a@example.com) [c](https://example.com) [d](SKILL.md#x)\n"
    assert check_structure(make(tmp_path, body(extra=extra))) == []


def test_reference_links_resolve_relative_to_their_file(tmp_path):
    refs = {"a.md": "[back](../SKILL.md) [bad](nope.md)\n"}
    found = check_structure(make(tmp_path, body(extra="[a](references/a.md)\n"), refs))
    assert messages(found) == ["broken relative link: nope.md"]
    assert found[0].path == Path("skills/k8s-demo-skill/references/a.md")


def test_unlinked_reference(tmp_path):
    found = check_structure(make(tmp_path, body(), {"a.md": "text\n"}))
    assert messages(found) == ["reference not linked from SKILL.md"]
    assert found[0].path == Path("skills/k8s-demo-skill/references/a.md")


def test_linked_reference_passes(tmp_path):
    skill = make(tmp_path, body(extra="[a](references/a.md)\n"), {"a.md": "text\n"})
    assert check_structure(skill) == []


def test_nested_references_are_link_checked_and_must_be_linked(tmp_path):
    skill_dir = make(tmp_path, body())
    nested = skill_dir / "references" / "deep"
    nested.mkdir(parents=True)
    (nested / "notes.md").write_text("[gone](missing.md)\n", encoding="utf-8")
    found = check_structure(skill_dir)
    assert (
        "skills/k8s-demo-skill/references/deep/notes.md",
        "broken relative link: missing.md",
    ) in {(str(f.path), f.message) for f in found}
    assert (
        "skills/k8s-demo-skill/references/deep/notes.md",
        "reference not linked from SKILL.md",
    ) in {(str(f.path), f.message) for f in found}

"""Tests for the frontmatter check: one test per rule in the skill format."""

from pathlib import Path

import pytest

from tools.skillcheck.frontmatter import check_frontmatter, parse_skill

GOOD = {
    "name": "k8s-pod-troubleshooting",
    "description": "Use when a pod is crashing.",
    "license": "Apache-2.0",
    "metadata": {"verified-with": "kind v1.37.0", "verified-on": '"2026-10-23"'},
}


def make_skill(
    root: Path,
    folder: str = "k8s-pod-troubleshooting",
    body: str = "# Body\n",
    raw: str | None = None,
    **overrides: object,
) -> Path:
    """Write skills/<folder>/SKILL.md under root and return the skill folder.

    Values in overrides replace the defaults; a value of None removes the field.
    """
    fields = {**GOOD, **overrides}
    lines = ["---"]
    for key, value in fields.items():
        if value is None:
            continue
        if isinstance(value, dict):
            lines.append(f"{key}:")
            lines += [f"  {k}: {v}" for k, v in value.items()]
        else:
            lines.append(f"{key}: {value}")
    lines += ["---", body]
    skill_dir = root / "skills" / folder
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(raw if raw is not None else "\n".join(lines))
    return skill_dir


def messages(skill_dir: Path) -> list[str]:
    return [f.message for f in check_frontmatter(skill_dir)]


def test_valid_skill_passes(tmp_path):
    assert check_frontmatter(make_skill(tmp_path)) == []


def test_parse_skill_returns_body_line(tmp_path):
    skill_dir = make_skill(tmp_path)
    meta, body, line = parse_skill(skill_dir / "SKILL.md")
    assert meta["name"] == "k8s-pod-troubleshooting"
    assert body.startswith("# Body")
    assert line == 9


def test_findings_use_repo_relative_path(tmp_path):
    findings = check_frontmatter(make_skill(tmp_path, license="MIT"))
    assert findings[0].path == Path("skills/k8s-pod-troubleshooting/SKILL.md")


def test_missing_frontmatter(tmp_path):
    skill_dir = make_skill(tmp_path, raw="# Just a body\n")
    assert any("no YAML frontmatter" in m for m in messages(skill_dir))


def test_unknown_field(tmp_path):
    skill_dir = make_skill(tmp_path, **{"disable-model-invocation": "true"})
    assert any("field not portable: disable-model-invocation" in m for m in messages(skill_dir))


def test_name_must_match_folder(tmp_path):
    skill_dir = make_skill(tmp_path, name="k8s-other")
    assert any("name must equal folder" in m for m in messages(skill_dir))


def test_name_needs_prefix(tmp_path):
    skill_dir = make_skill(
        tmp_path, folder="network-troubleshooting", name="network-troubleshooting"
    )
    assert any("name must start with k8s-" in m for m in messages(skill_dir))


@pytest.mark.parametrize("name", ["k8s--x", "K8s-x", "k8s-x-"])
def test_name_pattern(tmp_path, name):
    skill_dir = make_skill(tmp_path, folder=name, name=name)
    assert any("name must match" in m for m in messages(skill_dir))


def test_name_reserved_word(tmp_path):
    skill_dir = make_skill(tmp_path, folder="k8s-claude-x", name="k8s-claude-x")
    assert any("reserved word" in m for m in messages(skill_dir))


def test_description_must_start_use_when(tmp_path):
    skill_dir = make_skill(tmp_path, description="Troubleshoots pods.")
    assert any("description must start with 'Use when'" in m for m in messages(skill_dir))


def test_description_too_long(tmp_path):
    skill_dir = make_skill(tmp_path, description="Use when " + "x" * 1016)
    assert any("description longer than 1024" in m for m in messages(skill_dir))


def test_license_must_be_apache(tmp_path):
    skill_dir = make_skill(tmp_path, license="MIT")
    assert any("license must be Apache-2.0" in m for m in messages(skill_dir))


def test_metadata_values_are_strings(tmp_path):
    skill_dir = make_skill(
        tmp_path, metadata={"verified-with": "kind v1.37.0", "verified-on": "2026-10-23"}
    )
    assert any("metadata values must be strings" in m for m in messages(skill_dir))


def test_metadata_requires_verified_fields(tmp_path):
    skill_dir = make_skill(tmp_path, metadata={"other": "x"})
    found = messages(skill_dir)
    assert any("metadata.verified-with missing" in m for m in found)
    assert any("metadata.verified-on missing" in m for m in found)


def test_skill_md_too_long(tmp_path):
    skill_dir = make_skill(tmp_path, body="line\n" * 501)
    assert any("longer than 500 lines" in m for m in messages(skill_dir))

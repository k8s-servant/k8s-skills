"""Tests for the command line: exit codes and output of `check`."""

from pathlib import Path

from tools.skillcheck.__main__ import main

VALID = """---
name: k8s-demo-skill
description: Use when testing.
license: Apache-2.0
metadata:
  verified-with: kind
  verified-on: "2026-10-23"
---
"""
SECTIONS = (
    "".join(
        f"## {t}\n\ntext\n\n"
        for t in ("When to use", "Investigate", "Read the results", "Proposed fix", "Sources")
    )
    + "[docs](https://example.com)\n"
)


def add_skill(repo: Path, name: str, text: str | None) -> Path:
    folder = repo / "skills" / name
    folder.mkdir(parents=True)
    if text is not None:
        (folder / "SKILL.md").write_text(text, encoding="utf-8")
    return folder


def add_valid(repo: Path, name: str = "k8s-aks-demo") -> None:
    # A cloud-prefixed name skips the scenario requirement, so the skill stays minimal.
    add_skill(repo, name, VALID.replace("k8s-demo-skill", name) + SECTIONS)


def test_cli_exit_codes(tmp_path, capsys):
    add_valid(tmp_path)
    assert main(["check", "--repo", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "ok: 1 skills"

    add_skill(tmp_path, "k8s-aks-bad", VALID.replace("k8s-demo-skill", "k8s-aks-bad") + "text\n")
    assert main(["check", "--repo", str(tmp_path)]) == 1
    out = capsys.readouterr().out
    assert "skills/k8s-aks-bad/SKILL.md" in out
    assert "sections must be" in out
    assert "ok:" not in out


def test_cli_zero_skills(tmp_path, capsys):
    assert main(["check", "--repo", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "ok: 0 skills"


def test_cli_missing_skill_md_is_a_finding(tmp_path, capsys):
    add_skill(tmp_path, "k8s-aks-empty", None)
    assert main(["check", "--repo", str(tmp_path)]) == 1
    assert "skills/k8s-aks-empty: SKILL.md missing" in capsys.readouterr().out


def test_cli_bad_encoding_is_a_finding(tmp_path, capsys):
    folder = add_skill(tmp_path, "k8s-aks-bytes", None)
    (folder / "SKILL.md").write_bytes(b"---\n\xff\xfe\n---\n")
    assert main(["check", "--repo", str(tmp_path)]) == 1
    assert "k8s-aks-bytes" in capsys.readouterr().out


def test_cli_defaults_to_cwd(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert main(["check"]) == 0
    assert capsys.readouterr().out.strip() == "ok: 0 skills"

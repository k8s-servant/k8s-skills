"""Tests for the Finding type shared by every skillcheck check."""

from pathlib import Path

from tools.skillcheck.findings import Finding


def test_finding_str_with_and_without_line():
    assert str(Finding(Path("skills/a/SKILL.md"), 3, "bad")) == "skills/a/SKILL.md:3: bad"
    assert str(Finding(Path("skills/a"), None, "bad")) == "skills/a: bad"

"""Finds the skill folders of a repository, shared by every subcommand.

One definition keeps `check` and `manifests` looking at the same set of skills.
Folders starting with `.` or `_` are helpers, not skills; but a SKILL.md inside one is
reported by `check`, since agents that scan recursively would still find it.
"""

from pathlib import Path


def skill_dirs(repo: Path) -> list[Path]:
    """Return the sorted `skills/*/` folders, ignoring hidden and `__` helper folders."""
    skills_dir = repo / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(
        p for p in skills_dir.iterdir() if p.is_dir() and not p.name.startswith((".", "_"))
    )


def hidden_skill_dirs(repo: Path) -> list[Path]:
    """Return the sorted `skills/.*/` and `skills/_*/` folders that contain a SKILL.md."""
    skills_dir = repo / "skills"
    if not skills_dir.is_dir():
        return []
    return sorted(
        p
        for p in skills_dir.iterdir()
        if p.is_dir() and p.name.startswith((".", "_")) and (p / "SKILL.md").is_file()
    )

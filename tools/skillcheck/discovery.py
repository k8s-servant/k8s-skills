"""Finds the skill folders of a repository, shared by every subcommand.

One definition keeps `check` and `manifests` looking at the same set of skills.
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

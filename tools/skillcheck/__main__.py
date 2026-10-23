"""Command line for skillcheck: `python -m tools.skillcheck check [--repo PATH]`.

One entry point runs every check over every skill so CI and contributors run the same
thing. A broken skill folder must never crash the run: every problem, including an
unreadable file, becomes a finding so one bad skill cannot hide the others.
"""

import argparse
import sys
from pathlib import Path

from tools.skillcheck.commands import check_commands, load_allowlist
from tools.skillcheck.findings import Finding
from tools.skillcheck.frontmatter import check_frontmatter
from tools.skillcheck.scenarios import check_scenarios
from tools.skillcheck.structure import check_structure


def _check_skill(repo: Path, skill_dir: Path, allowlist: dict) -> list[Finding]:
    """Run every check on one skill folder, turning checker errors into findings."""
    rel = skill_dir.relative_to(repo)
    if not (skill_dir / "SKILL.md").is_file():
        return [Finding(rel, None, "SKILL.md missing")]
    found: list[Finding] = []
    checks = (
        lambda: check_frontmatter(skill_dir),
        lambda: check_structure(skill_dir),
        lambda: check_commands(skill_dir, allowlist),
        lambda: check_scenarios(repo, skill_dir),
    )
    for check in checks:
        try:
            found += check()
        except (ValueError, UnicodeDecodeError) as exc:
            found.append(Finding(rel / "SKILL.md", None, f"cannot check: {exc}"))
    return found


def run_check(repo: Path) -> int:
    """Check every `skills/*/` folder of a repository and print the result."""
    skills_dir = repo / "skills"
    skills = sorted(p for p in skills_dir.iterdir() if p.is_dir()) if skills_dir.is_dir() else []
    allowlist = load_allowlist()
    found: list[Finding] = []
    for skill_dir in skills:
        found += _check_skill(repo, skill_dir, allowlist)
    # Deduplicate: a file that cannot be parsed is reported by several checks alike.
    unique = sorted(set(found), key=lambda f: (str(f.path), f.line or 0, f.message))
    for finding in unique:
        print(finding)
    if unique:
        return 1
    print(f"ok: {len(skills)} skills")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns the process exit code."""
    parser = argparse.ArgumentParser(prog="skillcheck")
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check", help="check every skill in the repository")
    check.add_argument("--repo", type=Path, default=Path.cwd(), help="repository root")
    args = parser.parse_args(argv)
    return run_check(args.repo.resolve())


if __name__ == "__main__":
    sys.exit(main())

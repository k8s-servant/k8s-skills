"""Command line for skillcheck: `python -m tools.skillcheck check [--repo PATH]`.

One entry point runs every check over every skill so CI and contributors run the same
thing. A broken skill folder must never crash the run: every problem, including an
unreadable file, becomes a finding so one bad skill cannot hide the others.
"""

import argparse
import sys
from pathlib import Path

from tools.skillcheck.commands import check_commands, load_allowlist
from tools.skillcheck.discovery import skill_dirs
from tools.skillcheck.findings import Finding
from tools.skillcheck.frontmatter import check_frontmatter
from tools.skillcheck.manifests import ManifestError, check_manifests, write_manifests
from tools.skillcheck.package import package_skills
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
    skills = skill_dirs(repo)
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
    manifests = sub.add_parser("manifests", help="generate or verify the install manifests")
    manifests.add_argument("--repo", type=Path, default=Path.cwd(), help="repository root")
    mode = manifests.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write the files")
    mode.add_argument("--check", action="store_true", help="fail if a file is stale")
    package = sub.add_parser("package", help="zip every skill for a release")
    package.add_argument("--repo", type=Path, default=Path.cwd(), help="repository root")
    package.add_argument("--out", type=Path, required=True, help="output directory")
    args = parser.parse_args(argv)
    if args.command == "package":
        zips = package_skills(args.repo.resolve(), args.out)
        print(f"packaged {len(zips)} skills into {args.out}")
        return 0
    if args.command == "manifests":
        repo = args.repo.resolve()
        try:
            return write_manifests(repo) if args.write else check_manifests(repo)
        except ManifestError as exc:
            for problem in exc.problems:
                print(problem)
            print("run python -m tools.skillcheck check for details")
            return 1
    return run_check(args.repo.resolve())


if __name__ == "__main__":
    sys.exit(main())

"""Checks that each non-cloud skill ships runnable, guarded test scenarios.

A skill is only trusted once it has been run against a broken cluster. Each scenario
sets a failure up, breaks it, cleans up, and says what a correct answer looks like.
The scripts must refuse to run against anything but the throwaway test cluster, so the
guard call is checked here rather than trusted. Cloud skills (AKS, EKS, GKE) need a
real cloud account, so they need no minimum number of scenarios; the ones they have run
on a real cluster, so each names its platform and the one namespace it may use.
"""

import os
import re
from pathlib import Path

from markdown_it import MarkdownIt

from tools.skillcheck.findings import Finding

CLOUD_SKILL = re.compile(r"^k8s-(aks|eks|gke)-")
SCRIPTS = ("setup.sh", "break.sh", "cleanup.sh")
SOURCE_LINE = 'source "$(dirname "$0")/../../lib.sh"'
GUARD_CALL = "require_test_cluster"
EXPECTED_SECTIONS = ["Prompt", "Cause", "Evidence", "Acceptable fixes", "Wrong answers"]
MIN_SCENARIOS = 2
NO_PLATFORM = "a cloud scenario needs a platform file (aks, eks or gke)"
NO_SCOPE = "a cloud scenario must run in one namespace: add agent-scope"
KIND_ONLY = "only cloud skills (k8s-aks-*, k8s-eks-*, k8s-gke-*) run on a real cluster"


def is_cloud_skill(name: str) -> bool:
    """True for skills about a managed cloud (k8s-aks-*, k8s-eks-*, k8s-gke-*)."""
    return bool(CLOUD_SKILL.match(name))


def _h2_titles(text: str) -> list[str]:
    """Return the H2 titles of a Markdown text, in order."""
    tokens = MarkdownIt("commonmark").parse(text)
    return [
        tokens[i + 1].content.strip()
        for i, t in enumerate(tokens)
        if t.type == "heading_open" and t.tag == "h2"
    ]


def check_orphan_tests(repo: Path) -> list[Finding]:
    """Report `tests/<name>/` folders with no `skills/<name>/`, left behind by a rename.

    Files in `tests/` (the kit) and `.`/`_` folders are not scenario folders.
    """
    tests_dir = repo / "tests"
    if not tests_dir.is_dir():
        return []
    return [
        Finding(folder.relative_to(repo), None, "test folder has no matching skill")
        for folder in sorted(tests_dir.iterdir())
        if folder.is_dir()
        and not folder.name.startswith((".", "_"))
        and not (repo / "skills" / folder.name).is_dir()
    ]


def check_scenarios(repo: Path, skill_dir: Path) -> list[Finding]:
    """Check the scenarios of one skill under `tests/<skill>/`.

    Args:
        repo: The repository root.
        skill_dir: A `<repo>/skills/<name>` folder.

    Returns:
        One Finding per broken rule, with paths relative to the repository root.
    """
    cloud = is_cloud_skill(skill_dir.name)
    tests_dir = repo / "tests" / skill_dir.name
    cases = sorted(p for p in tests_dir.iterdir() if p.is_dir()) if tests_dir.is_dir() else []
    found: list[Finding] = []
    if not cloud and len(cases) < MIN_SCENARIOS:
        rel = tests_dir.relative_to(repo)
        found.append(Finding(rel, None, f"needs at least two scenarios in {rel}/"))

    for case in cases:
        for name in SCRIPTS:
            script = case / name
            rel = script.relative_to(repo)
            if not script.is_file():
                found.append(Finding(rel, None, "missing"))
                continue
            if not os.access(script, os.X_OK):
                found.append(Finding(rel, None, "not executable"))
            text = script.read_text(encoding="utf-8")
            if SOURCE_LINE not in text:
                found.append(Finding(rel, None, "must source lib.sh"))
            if GUARD_CALL not in text.replace(SOURCE_LINE, ""):
                found.append(Finding(rel, None, f"must call {GUARD_CALL}"))

        if cloud:
            for name, message in (("platform", NO_PLATFORM), ("agent-scope", NO_SCOPE)):
                if not (case / name).is_file():
                    found.append(Finding((case / name).relative_to(repo), None, message))
        elif (case / "platform").exists():
            found.append(Finding((case / "platform").relative_to(repo), None, KIND_ONLY))

        expected = case / "expected.md"
        rel = expected.relative_to(repo)
        if not expected.is_file():
            found.append(Finding(rel, None, "missing"))
        elif _h2_titles(expected.read_text(encoding="utf-8")) != EXPECTED_SECTIONS:
            found.append(Finding(rel, None, f"sections must be: {', '.join(EXPECTED_SECTIONS)}"))
    return found

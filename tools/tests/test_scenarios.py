"""Tests for the scenario check: every non-cloud skill ships guarded test cases."""

import stat
from pathlib import Path

from tools.skillcheck.scenarios import check_scenarios, is_cloud_skill

SCRIPT = '#!/usr/bin/env bash\nsource "$(dirname "$0")/../../lib.sh"\nrequire_test_cluster\n'
EXPECTED = "".join(
    f"## {t}\n\ntext\n\n"
    for t in ("Prompt", "Cause", "Evidence", "Acceptable fixes", "Wrong answers")
)


def make_case(repo: Path, skill: str, case: str, **overrides: str | None) -> Path:
    """Create tests/<skill>/<case> with valid files; override or drop (None) per file."""
    folder = repo / "tests" / skill / case
    folder.mkdir(parents=True)
    files = {
        "setup.sh": SCRIPT,
        "break.sh": SCRIPT,
        "cleanup.sh": SCRIPT,
        "expected.md": EXPECTED,
    }
    files.update(overrides)
    for name, text in files.items():
        if text is None:
            continue
        target = folder / name
        target.write_text(text, encoding="utf-8")
        if name.endswith(".sh"):
            target.chmod(0o755)
    return folder


def skill(repo: Path, name: str = "k8s-pod-crashloop") -> Path:
    path = repo / "skills" / name
    path.mkdir(parents=True)
    return path


def messages(findings: list) -> list[str]:
    return [f.message for f in findings]


def test_is_cloud_skill():
    assert is_cloud_skill("k8s-aks-upgrade")
    assert is_cloud_skill("k8s-eks-nodes")
    assert is_cloud_skill("k8s-gke-quota")
    assert not is_cloud_skill("k8s-pod-crashloop")
    assert not is_cloud_skill("k8s-aksfoo-bar")


def test_cloud_skill_needs_no_scenarios(tmp_path):
    assert check_scenarios(tmp_path, skill(tmp_path, "k8s-aks-upgrade")) == []


def test_needs_two_scenarios(tmp_path):
    sk = skill(tmp_path)
    assert messages(check_scenarios(tmp_path, sk)) == [
        "needs at least two scenarios in tests/k8s-pod-crashloop/"
    ]
    make_case(tmp_path, sk.name, "one")
    assert len(check_scenarios(tmp_path, sk)) == 1
    make_case(tmp_path, sk.name, "two")
    assert check_scenarios(tmp_path, sk) == []


def test_scenario_files_and_exec_bits(tmp_path):
    sk = skill(tmp_path)
    make_case(tmp_path, sk.name, "one", **{"expected.md": None})
    two = make_case(tmp_path, sk.name, "two")
    two.joinpath("break.sh").chmod(0o644)
    found = check_scenarios(tmp_path, sk)
    assert sorted(f"{f.path.name}: {f.message}" for f in found) == [
        "break.sh: not executable",
        "expected.md: missing",
    ]
    assert stat.S_IMODE(two.joinpath("setup.sh").stat().st_mode) == 0o755


def test_scenario_script_must_use_guard(tmp_path):
    sk = skill(tmp_path)
    make_case(
        tmp_path, sk.name, "one", **{"setup.sh": "#!/usr/bin/env bash\nrequire_test_cluster\n"}
    )
    make_case(tmp_path, sk.name, "two", **{"break.sh": SCRIPT.replace("require_test_cluster", "")})
    found = check_scenarios(tmp_path, sk)
    assert sorted(f"{f.path.name}: {f.message}" for f in found) == [
        "break.sh: must call require_test_cluster",
        "setup.sh: must source lib.sh",
    ]


def test_expected_sections(tmp_path):
    sk = skill(tmp_path)
    make_case(tmp_path, sk.name, "one", **{"expected.md": "## Prompt\n\nx\n\n## Cause\n\ny\n"})
    make_case(tmp_path, sk.name, "two")
    found = check_scenarios(tmp_path, sk)
    assert messages(found) == [
        "sections must be: Prompt, Cause, Evidence, Acceptable fixes, Wrong answers"
    ]
    assert found[0].path == Path("tests/k8s-pod-crashloop/one/expected.md")


def test_test_folder_without_a_skill_is_a_finding(tmp_path):
    from tools.skillcheck.scenarios import check_orphan_tests

    skill(tmp_path, "k8s-pod-crashloop")
    make_case(tmp_path, "k8s-pod-crashloop", "a")
    make_case(tmp_path, "k8s-old-skill", "a")
    (tmp_path / "tests" / "lib.sh").write_text("# kit file\n", encoding="utf-8")
    (tmp_path / "tests" / "__pycache__").mkdir()
    found = check_orphan_tests(tmp_path)
    assert [(str(f.path), f.message) for f in found] == [
        ("tests/k8s-old-skill", "test folder has no matching skill")
    ]


def test_no_tests_folder_means_no_orphans(tmp_path):
    from tools.skillcheck.scenarios import check_orphan_tests

    assert check_orphan_tests(tmp_path) == []


def test_cloud_scenarios_are_checked_and_need_platform_and_scope(tmp_path):
    sk = skill(tmp_path, "k8s-aks-troubleshooting")
    make_case(tmp_path, sk.name, "good", platform="aks\n", **{"agent-scope": "my-namespace\n"})
    make_case(tmp_path, sk.name, "bare", **{"break.sh": None})
    found = {(f.path.as_posix(), f.message) for f in check_scenarios(tmp_path, sk)}
    base = "tests/k8s-aks-troubleshooting/bare"
    assert found == {
        (f"{base}/break.sh", "missing"),
        (f"{base}/platform", "a cloud scenario needs a platform file (aks, eks or gke)"),
        (f"{base}/agent-scope", "a cloud scenario must run in one namespace: add agent-scope"),
    }


def test_kind_scenario_cannot_name_a_platform(tmp_path):
    sk = skill(tmp_path)
    make_case(tmp_path, sk.name, "one")
    make_case(tmp_path, sk.name, "two", platform="aks\n")
    assert messages(check_scenarios(tmp_path, sk)) == [
        "only cloud skills (k8s-aks-*, k8s-eks-*, k8s-gke-*) run on a real cluster"
    ]

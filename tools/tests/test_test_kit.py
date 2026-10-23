"""Tests for the kind test kit: the context guard, cluster.sh and run.sh.

The scripts run against fake ``kubectl`` and ``kind`` executables placed first on
PATH, inside a throwaway copy of the repo layout, so the tests never touch a real
cluster or the real ``.kube/`` folder.
"""

import os
import shutil
import subprocess
from pathlib import Path

REAL_TESTS = Path(__file__).resolve().parents[2] / "tests"
CONTEXT = "kind-k8s-skills-test"
REFUSAL = f"refusing to run: current context is not {CONTEXT}"

FAKE_KUBECTL = """#!/usr/bin/env bash
echo "kubectl $*" >> "$FAKE_LOG"
case "$1 $2" in
  "config current-context") echo "${FAKE_CONTEXT:-}" ;;
  "create token") echo "fake-token" ;;
esac
"""
FAKE_KIND = """#!/usr/bin/env bash
echo "kind $*" >> "$FAKE_LOG"
"""


def make_repo(tmp_path: Path) -> Path:
    """Copy the kit's scripts into a tmp repo and put fake kubectl/kind on PATH."""
    repo = tmp_path / "repo"
    shutil.copytree(REAL_TESTS, repo / "tests", ignore=shutil.ignore_patterns("k8s-*"))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, text in (("kubectl", FAKE_KUBECTL), ("kind", FAKE_KIND)):
        path = bin_dir / name
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)
    return repo


def run(tmp_path: Path, repo: Path, args: list[str], context: str = CONTEXT, **env: str):
    """Run a command with the fakes first on PATH; returns the CompletedProcess."""
    full_env = {
        **os.environ,
        "PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}",
        "FAKE_LOG": str(tmp_path / "calls.log"),
        "FAKE_CONTEXT": context,
        **env,
    }
    return subprocess.run(args, cwd=repo, env=full_env, capture_output=True, text=True, check=False)


def calls(tmp_path: Path) -> list[str]:
    log = tmp_path / "calls.log"
    return log.read_text().splitlines() if log.exists() else []


def guard(tmp_path: Path, repo: Path, **kw):
    cmd = 'source tests/lib.sh; require_test_cluster; echo "KUBECONFIG=$KUBECONFIG"'
    return run(tmp_path, repo, ["bash", "-c", cmd], **kw)


def make_kubeconfig(repo: Path) -> None:
    (repo / ".kube").mkdir()
    (repo / ".kube" / "k8s-skills-test").write_text("fake", encoding="utf-8")


def test_guard_refuses_other_context(tmp_path):
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    result = guard(tmp_path, repo, context="aks-prod")
    assert result.returncode == 2
    assert REFUSAL in result.stderr
    assert not any(c.startswith("kubectl apply") for c in calls(tmp_path))


def test_guard_refuses_unset_kubeconfig(tmp_path):
    repo = make_repo(tmp_path)
    # The caller's KUBECONFIG points elsewhere: lib.sh must overwrite it.
    make_kubeconfig(repo)
    ok = guard(tmp_path, repo, KUBECONFIG="/somewhere/else")
    assert ok.returncode == 0
    assert f"KUBECONFIG={repo}/.kube/k8s-skills-test" in ok.stdout
    # The test cluster's kubeconfig file is missing: refuse even with a good context.
    (repo / ".kube" / "k8s-skills-test").unlink()
    missing = guard(tmp_path, repo, KUBECONFIG="/somewhere/else")
    assert missing.returncode == 2
    assert REFUSAL in missing.stderr


def test_cluster_down_only_deletes_test_cluster(tmp_path):
    repo = make_repo(tmp_path)
    result = run(tmp_path, repo, ["tests/cluster.sh", "down"], KUBECONFIG="/somewhere/else")
    assert result.returncode == 0, result.stderr
    assert calls(tmp_path) == ["kind delete cluster --name k8s-skills-test"]


def test_run_prints_prompt(tmp_path):
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    case = repo / "tests" / "k8s-demo-skill" / "case-one"
    case.mkdir(parents=True)
    for name in ("setup.sh", "break.sh", "cleanup.sh"):
        script = case / name
        script.write_text(f'#!/usr/bin/env bash\necho "ran {name}" >&2\n', encoding="utf-8")
        script.chmod(0o755)
    (case / "expected.md").write_text(
        "## Prompt\n\nWhy is my-app crashing?\n\n## Cause\n\nsecret text\n", encoding="utf-8"
    )
    result = run(tmp_path, repo, ["tests/run.sh", "k8s-demo-skill", "case-one"])
    assert result.returncode == 0, result.stderr
    assert "Why is my-app crashing?" in result.stdout
    assert "secret text" not in result.stdout
    assert f"KUBECONFIG={repo}/.kube/agent" in result.stdout
    assert result.stderr.index("ran setup.sh") < result.stderr.index("ran break.sh")

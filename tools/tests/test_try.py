"""Tests for tests/try.sh: try one scenario on a throwaway kind cluster with your own agent.

Like the other kit tests, these run against fake kind, kubectl and docker executables, in a
throwaway copy of the repo layout.
"""

from pathlib import Path

from tools.tests.test_test_kit import calls, make_kubeconfig, make_repo, run

SKILL, CASE = "k8s-workload-troubleshooting", "oom-killed"


def make_scenario(repo: Path, skill: str = SKILL, case: str = CASE, platform: str = "") -> Path:
    folder = repo / "tests" / skill / case
    folder.mkdir(parents=True)
    for name in ("setup.sh", "break.sh", "cleanup.sh"):
        script = folder / name
        # Setup scripts print kubectl's output, which must not end up in the prompt.
        body = f'echo "{name}" >> "$FAKE_LOG"\necho "namespace/my-namespace created"\n'
        script.write_text(f"#!/usr/bin/env bash\n{body}", encoding="utf-8")
        script.chmod(0o755)
    (folder / "expected.md").write_text(
        "## Prompt\n\nmy-app keeps restarting. Find out why.\n\n## Cause\n\nthe answer\n",
        encoding="utf-8",
    )
    if platform:
        (folder / "platform").write_text(f"{platform}\n", encoding="utf-8")
    return folder


def try_repo(tmp_path: Path) -> Path:
    repo = make_repo(tmp_path)
    docker = tmp_path / "bin" / "docker"
    docker.write_text('#!/usr/bin/env bash\necho "docker $*" >> "$FAKE_LOG"\n', encoding="utf-8")
    docker.chmod(0o755)
    make_kubeconfig(repo)
    return repo


def test_try_lists_the_kind_scenarios(tmp_path):
    repo = try_repo(tmp_path)
    make_scenario(repo)
    make_scenario(repo, "k8s-aks-troubleshooting", "cloud-only", platform="aks")
    result = run(tmp_path, repo, ["tests/try.sh", "--list"])
    assert result.returncode == 0, result.stderr
    assert f"{SKILL} {CASE}" in result.stdout
    assert "cloud-only" not in result.stdout


def test_try_creates_the_cluster_when_missing_and_breaks_the_default_scenario(tmp_path):
    repo = try_repo(tmp_path)
    make_scenario(repo)
    result = run(tmp_path, repo, ["tests/try.sh"])
    assert result.returncode == 0, result.stderr
    log = calls(tmp_path)
    create = next(i for i, c in enumerate(log) if c.startswith("kind create cluster"))
    assert create < log.index("setup.sh") < log.index("break.sh")
    assert "my-app keeps restarting. Find out why." in result.stdout
    assert f"export KUBECONFIG={repo}/.kube/agent" in result.stdout
    assert "the answer" not in result.stdout
    ask = result.stdout.split("Ask it:", 1)[1].split("The identity", 1)[0]
    assert ask.strip() == "my-app keeps restarting. Find out why."
    assert f"tests/{SKILL}/{CASE}/expected.md" in result.stdout
    assert f"tests/try.sh --cleanup {SKILL} {CASE}" in result.stdout
    assert "tests/try.sh --down" in result.stdout


def test_try_reuses_a_running_cluster(tmp_path):
    repo = try_repo(tmp_path)
    make_scenario(repo)
    result = run(tmp_path, repo, ["tests/try.sh"], FAKE_KIND_CLUSTERS="k8s-skills-test")
    assert result.returncode == 0, result.stderr
    assert not any(c.startswith("kind create cluster") for c in calls(tmp_path))
    assert "break.sh" in calls(tmp_path)


def test_try_runs_a_named_scenario(tmp_path):
    repo = try_repo(tmp_path)
    make_scenario(repo, "k8s-demo-skill", "case-two")
    result = run(
        tmp_path,
        repo,
        ["tests/try.sh", "k8s-demo-skill", "case-two"],
        FAKE_KIND_CLUSTERS="k8s-skills-test",
    )
    assert result.returncode == 0, result.stderr
    assert "tests/try.sh --cleanup k8s-demo-skill case-two" in result.stdout


def test_try_refuses_a_cloud_scenario(tmp_path):
    repo = try_repo(tmp_path)
    make_scenario(repo, "k8s-aks-troubleshooting", "cloud-only", platform="aks")
    result = run(
        tmp_path,
        repo,
        ["tests/try.sh", "k8s-aks-troubleshooting", "cloud-only"],
        FAKE_KIND_CLUSTERS="k8s-skills-test",
    )
    assert result.returncode != 0
    assert "kind" in result.stderr
    assert "setup.sh" not in calls(tmp_path)


def test_try_cleanup_and_down(tmp_path):
    repo = try_repo(tmp_path)
    make_scenario(repo)
    cleanup = run(tmp_path, repo, ["tests/try.sh", "--cleanup"])
    assert cleanup.returncode == 0, cleanup.stderr
    assert "cleanup.sh" in calls(tmp_path)
    down = run(tmp_path, repo, ["tests/try.sh", "--down"])
    assert down.returncode == 0, down.stderr
    assert "kind delete cluster --name k8s-skills-test" in calls(tmp_path)


def test_try_needs_kind_kubectl_and_docker(tmp_path):
    repo = try_repo(tmp_path)
    make_scenario(repo)
    (tmp_path / "bin" / "kind").unlink()
    # Only the fakes and the base system: no real kind anywhere on PATH.
    result = run(tmp_path, repo, ["tests/try.sh"], PATH=f"{tmp_path / 'bin'}:/usr/bin:/bin")
    assert result.returncode != 0
    assert "kind" in result.stderr
    assert "setup.sh" not in calls(tmp_path)

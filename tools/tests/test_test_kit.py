"""Tests for the kind test kit: the context guard, cluster.sh and run.sh.

The scripts run against fake ``kubectl`` and ``kind`` executables placed first on
PATH, inside a throwaway copy of the repo layout, so the tests never touch a real
cluster or the real ``.kube/`` folder.
"""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REAL_TESTS = Path(__file__).resolve().parents[2] / "tests"
CONTEXT = "kind-k8s-skills-test"
REFUSAL = f"refusing to run: current context is not {CONTEXT}"

FAKE_KUBECTL = """#!/usr/bin/env bash
echo "kubectl $*" >> "$FAKE_LOG"
if [[ "$1 $2 $3" == "apply -f -" ]]; then cat >> "$FAKE_STDIN"; fi
case "$1 $2" in
  "config current-context") echo "${FAKE_CONTEXT:-}" ;;
  "create token") echo "fake-token" ;;
  "get namespace") exit 1 ;;  # the fake cluster has no namespaces yet
  "config view") echo "client-certificate-data: FAKE-ADMIN-CERT" ;;
  "config --kubeconfig")
    # Record whether the agent's final path holds admin credentials at this moment.
    if grep -qs FAKE-ADMIN-CERT "${FAKE_AGENT:-/nonexistent}"; then
      echo "agent file holds admin credentials" >> "$FAKE_LOG"
    fi
    if [[ "$4" == "delete-user" ]]; then
      grep -v FAKE-ADMIN-CERT "$3" > "$3.new" || true
      mv "$3.new" "$3"
    fi
    ;;
esac
"""
FAKE_CURL = """#!/usr/bin/env bash
echo "curl $*" >> "$FAKE_LOG"
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "-o" ]]; then printf 'fake calico manifest\n' > "$2"; fi
  shift
done
"""
FAKE_MKTEMP = """#!/usr/bin/env bash
dir="${FAKE_TMP:-$(dirname "$FAKE_LOG")}"
file="$dir/tmp.$$.$RANDOM"
: > "$file"
echo "$file"
"""
FAKE_KIND = """#!/usr/bin/env bash
echo "kind $*" >> "$FAKE_LOG"
if [[ -n "${FAKE_KIND_FAIL:-}" ]]; then exit 1; fi
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "--config" ]]; then cat "$2" >> "$FAKE_LOG"; fi
  shift
done
"""


def make_repo(tmp_path: Path) -> Path:
    """Copy the kit's scripts into a tmp repo and put fake kubectl/kind on PATH."""
    repo = tmp_path / "repo"
    shutil.copytree(REAL_TESTS, repo / "tests", ignore=shutil.ignore_patterns("k8s-*"))
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, text in (
        ("kubectl", FAKE_KUBECTL),
        ("kind", FAKE_KIND),
        ("curl", FAKE_CURL),
        ("mktemp", FAKE_MKTEMP),
    ):
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
        "FAKE_STDIN": str(tmp_path / "applied.yaml"),
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


def test_run_prompt_heading_tolerates_trailing_spaces(tmp_path):
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    case = repo / "tests" / "k8s-demo-skill" / "case-one"
    case.mkdir(parents=True)
    for name in ("setup.sh", "break.sh", "cleanup.sh"):
        script = case / name
        script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        script.chmod(0o755)
    (case / "expected.md").write_text(
        "## Prompt  \n\nWhy is my-app crashing?\n\n## Cause \n\nsecret text\n",
        encoding="utf-8",
    )
    result = run(tmp_path, repo, ["tests/run.sh", "k8s-demo-skill", "case-one"])
    assert result.returncode == 0, result.stderr
    assert "Why is my-app crashing?" in result.stdout
    assert "secret text" not in result.stdout


def applied(tmp_path: Path) -> str:
    """The YAML the scripts piped into `kubectl apply -f -`."""
    path = tmp_path / "applied.yaml"
    return path.read_text() if path.exists() else ""


def test_agent_kubeconfig_cluster_scope(tmp_path):
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    result = run(tmp_path, repo, ["tests/agent-kubeconfig.sh"])
    assert result.returncode == 0, result.stderr
    yaml_text = applied(tmp_path)
    assert "kind: ClusterRoleBinding" in yaml_text
    assert "name: view" in yaml_text
    assert "name: skill-agent-cluster-reader" in yaml_text
    for resource in (
        "nodes",
        "persistentvolumes",
        "storageclasses",
        "csidrivers",
        "csinodes",
        "volumeattachments",
        "clusterissuers",
        "validatingwebhookconfigurations",
        "mutatingwebhookconfigurations",
        "applications",
        "applicationsets",
        "appprojects",
        "constrainttemplates",
        "validatingadmissionpolicies",
        "clusterexternalsecrets",
    ):
        assert f"- {resource}" in yaml_text, resource
    # Prometheus' and Alertmanager's HTTP APIs, through the API server's service proxy,
    # on their two governing Services only.
    assert "- services/proxy" in yaml_text
    # RBAC sees a proxied service with its port in the name ("prometheus-operated:web").
    for name in ("prometheus-operated", "prometheus-operated:web", "alertmanager-operated:web"):
        assert f'"{name}"' in yaml_text, name


def test_agent_kubeconfig_never_holds_admin_credentials(tmp_path):
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    agent = repo / ".kube" / "agent"
    result = run(tmp_path, repo, ["tests/agent-kubeconfig.sh"], FAKE_AGENT=str(agent))
    assert result.returncode == 0, result.stderr
    assert "agent file holds admin credentials" not in calls(tmp_path)
    assert agent.exists()
    assert "FAKE-ADMIN-CERT" not in agent.read_text()
    assert result.stdout.strip() == str(agent)


def test_agent_kubeconfig_namespace_scope(tmp_path):
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    result = run(tmp_path, repo, ["tests/agent-kubeconfig.sh", "--namespace", "my-namespace"])
    assert result.returncode == 0, result.stderr
    yaml_text = applied(tmp_path)
    assert "kind: RoleBinding" in yaml_text
    assert "namespace: my-namespace" in yaml_text
    assert "ClusterRoleBinding" not in yaml_text
    assert "nodes" not in yaml_text
    assert "storageclasses" not in yaml_text


def test_agent_kubeconfig_rejects_bad_arguments(tmp_path):
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    for args in (["--namespace"], ["--bogus"]):
        result = run(tmp_path, repo, ["tests/agent-kubeconfig.sh", *args])
        assert result.returncode == 64, (args, result.stderr)
        assert "usage:" in result.stderr


def test_run_uses_agent_scope(tmp_path):
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    case = repo / "tests" / "k8s-demo-skill" / "case-one"
    case.mkdir(parents=True)
    for name in ("setup.sh", "break.sh", "cleanup.sh"):
        script = case / name
        script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        script.chmod(0o755)
    (case / "expected.md").write_text("## Prompt\n\nIs it broken?\n", encoding="utf-8")
    (case / "agent-scope").write_text("my-namespace\n", encoding="utf-8")
    result = run(tmp_path, repo, ["tests/run.sh", "k8s-demo-skill", "case-one"])
    assert result.returncode == 0, result.stderr
    yaml_text = applied(tmp_path)
    assert "kind: RoleBinding" in yaml_text
    assert "namespace: my-namespace" in yaml_text
    assert "ClusterRoleBinding" not in yaml_text


def test_run_works_without_agent_scope_on_old_bash(tmp_path):
    """macOS ships bash 3.2, where an empty array under `set -u` is an error."""
    system_bash = Path("/bin/bash")
    if not system_bash.exists():
        return
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    (tmp_path / "bin" / "bash").symlink_to(system_bash)
    case = repo / "tests" / "k8s-demo-skill" / "case-one"
    case.mkdir(parents=True)
    for name in ("setup.sh", "break.sh", "cleanup.sh"):
        script = case / name
        script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        script.chmod(0o755)
    (case / "expected.md").write_text("## Prompt\n\nIs it broken?\n", encoding="utf-8")
    result = run(tmp_path, repo, ["tests/run.sh", "k8s-demo-skill", "case-one"])
    assert result.returncode == 0, result.stderr
    assert "kind: ClusterRoleBinding" in applied(tmp_path)


def test_cluster_up_with_workers(tmp_path):
    repo = make_repo(tmp_path)
    result = run(tmp_path, repo, ["tests/cluster.sh", "up", "--workers", "1"])
    assert result.returncode == 0, result.stderr
    log = "\n".join(calls(tmp_path))
    assert log.count("role: worker") == 1
    assert log.count("role: control-plane") == 1
    assert "disableDefaultCNI" not in log


def test_cluster_up_with_cni_and_workers(tmp_path):
    repo = make_repo(tmp_path)
    pin_calico_checksum(repo, fake_manifest_checksum())
    result = run(tmp_path, repo, ["tests/cluster.sh", "up", "--cni", "calico", "--workers", "2"])
    assert result.returncode == 0, result.stderr
    log = "\n".join(calls(tmp_path))
    assert log.count("role: worker") == 2
    assert "disableDefaultCNI: true" in log


def test_cluster_up_rejects_bad_workers(tmp_path):
    repo = make_repo(tmp_path)
    for value in ("0", "x", ""):
        result = run(tmp_path, repo, ["tests/cluster.sh", "up", "--workers", value])
        assert result.returncode == 64, (value, result.stderr)


def test_agent_kubeconfig_removes_earlier_bindings(tmp_path):
    """A namespace-only run after a cluster-wide one must not keep cluster-wide access."""
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    for args in ([], ["--namespace", "my-namespace"]):
        (tmp_path / "calls.log").unlink(missing_ok=True)
        result = run(tmp_path, repo, ["tests/agent-kubeconfig.sh", *args])
        assert result.returncode == 0, result.stderr
        log = calls(tmp_path)
        cleanup = [
            (
                "kubectl delete clusterrolebinding skill-agent-view skill-agent-node-reader"
                " skill-agent-cluster-reader --ignore-not-found"
            ),
            (
                "kubectl delete rolebindings --all-namespaces"
                " --field-selector metadata.name=skill-agent-view --ignore-not-found"
            ),
        ]
        for line in cleanup:
            assert line in log, (args, log)
        # The cleanup runs before the bindings for this run are applied.
        applies = [i for i, c in enumerate(log) if c == "kubectl apply -f -"]
        assert max(log.index(line) for line in cleanup) < applies[-1], (args, log)


def test_run_strips_agent_scope_whitespace(tmp_path):
    """A CRLF checkout or a trailing space must not end up in the namespace name."""
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    case = repo / "tests" / "k8s-demo-skill" / "case-one"
    case.mkdir(parents=True)
    for name in ("setup.sh", "break.sh", "cleanup.sh"):
        script = case / name
        script.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
        script.chmod(0o755)
    (case / "expected.md").write_text("## Prompt\n\nIs it broken?\n", encoding="utf-8")
    (case / "agent-scope").write_bytes(b"my-namespace \r\n")
    result = run(tmp_path, repo, ["tests/run.sh", "k8s-demo-skill", "case-one"])
    assert result.returncode == 0, result.stderr
    assert "  namespace: my-namespace\n" in applied(tmp_path)


def test_agent_kubeconfig_namespace_scope_sets_context_namespace(tmp_path):
    """Like a developer's kubeconfig, the namespace-only agent's context points at its namespace."""
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    result = run(tmp_path, repo, ["tests/agent-kubeconfig.sh", "--namespace", "my-namespace"])
    assert result.returncode == 0, result.stderr
    assert any(
        c.startswith("kubectl config --kubeconfig ")
        and c.endswith(" set-context --current --namespace=my-namespace")
        for c in calls(tmp_path)
    )
    run(tmp_path, repo, ["tests/agent-kubeconfig.sh"])
    assert sum("--namespace=" in c for c in calls(tmp_path)) == 1


def pin_calico_checksum(repo: Path, checksum: str) -> None:
    versions = repo / "tests" / "versions.env"
    lines = [
        line
        for line in versions.read_text().splitlines()
        if not line.startswith("CALICO_MANIFEST_SHA256=")
    ]
    versions.write_text("\n".join([*lines, f"CALICO_MANIFEST_SHA256={checksum}"]) + "\n")


def fake_manifest_checksum() -> str:
    return hashlib.sha256(b"fake calico manifest\n").hexdigest()


def test_cluster_up_calico_applies_a_verified_manifest_and_waits(tmp_path):
    repo = make_repo(tmp_path)
    pin_calico_checksum(repo, fake_manifest_checksum())
    result = run(tmp_path, repo, ["tests/cluster.sh", "up", "--cni", "calico"])
    assert result.returncode == 0, result.stderr
    log = calls(tmp_path)
    applies = [c for c in log if c.startswith("kubectl apply -f ")]
    assert len(applies) == 1 and "https://" not in applies[0], log
    waits = [c for c in log if "rollout status daemonset/calico-node -n kube-system" in c]
    assert waits, log
    assert log.index(applies[0]) < log.index(waits[0])


def test_cluster_up_calico_refuses_a_manifest_with_the_wrong_checksum(tmp_path):
    repo = make_repo(tmp_path)
    pin_calico_checksum(repo, "0" * 64)
    result = run(tmp_path, repo, ["tests/cluster.sh", "up", "--cni", "calico"])
    assert result.returncode != 0
    assert "checksum" in result.stderr
    assert not [c for c in calls(tmp_path) if c.startswith("kubectl apply")]
    assert not [c for c in calls(tmp_path) if c.startswith("kind create")]


def test_cluster_up_calico_removes_the_manifest_when_kind_fails(tmp_path):
    repo = make_repo(tmp_path)
    pin_calico_checksum(repo, fake_manifest_checksum())
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    result = run(
        tmp_path,
        repo,
        ["tests/cluster.sh", "up", "--cni", "calico"],
        FAKE_TMP=str(scratch),
        FAKE_KIND_FAIL="1",
    )
    assert result.returncode != 0
    assert list(scratch.iterdir()) == []


def pin_version(repo: Path, key: str, value: str) -> None:
    versions = repo / "tests" / "versions.env"
    lines = [line for line in versions.read_text().splitlines() if not line.startswith(f"{key}=")]
    versions.write_text("\n".join([*lines, f"{key}={value}"]) + "\n")


ADDONS = [
    ("cert-manager", "CERT_MANAGER_MANIFEST_SHA256", "cert-manager.yaml", "cert-manager"),
    ("flux", "FLUX_MANIFEST_SHA256", "install.yaml", "flux-system"),
    ("argocd", "ARGOCD_MANIFEST_SHA256", "install.yaml", "argocd"),
    ("kyverno", "KYVERNO_MANIFEST_SHA256", "install.yaml", "kyverno"),
    ("gatekeeper", "GATEKEEPER_MANIFEST_SHA256", "gatekeeper.yaml", "gatekeeper-system"),
    # The release manifest is `helm template` output pinned to the default namespace.
    ("external-secrets", "ESO_MANIFEST_SHA256", "external-secrets.yaml", "default"),
    ("prometheus-operator", "PROMETHEUS_OPERATOR_MANIFEST_SHA256", "bundle.yaml", "default"),
]


@pytest.mark.parametrize(("name", "sha_key", "asset", "namespace"), ADDONS)
def test_addon_applies_a_verified_manifest_and_waits(tmp_path, name, sha_key, asset, namespace):
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    pin_version(repo, sha_key, fake_manifest_checksum())
    scratch = tmp_path / "tmp"
    scratch.mkdir()
    result = run(tmp_path, repo, ["tests/addon.sh", name], FAKE_TMP=str(scratch))
    assert result.returncode == 0, result.stderr
    log = calls(tmp_path)
    fetches = [c for c in log if c.startswith("curl ")]
    assert len(fetches) == 1 and asset in fetches[0], log
    applies = [c for c in log if c.startswith("kubectl apply ") and " -f " in c]
    assert len(applies) == 1 and "https://" not in applies[0], log
    # Server-side, so CRDs over the client-side annotation limit apply; into the
    # add-on's namespace, which exists first, for manifests whose objects carry none.
    assert "--server-side" in applies[0] and f"-n {namespace}" in applies[0], log
    creates = [c for c in log if f"create namespace {namespace}" in c]
    assert creates and log.index(creates[0]) < log.index(applies[0]), log
    waits = [c for c in log if c.startswith("kubectl wait") and f"-n {namespace}" in c]
    assert waits, log
    assert log.index(applies[0]) < log.index(waits[0])
    assert list(scratch.iterdir()) == []


def test_addon_refuses_a_manifest_with_the_wrong_checksum(tmp_path):
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    pin_version(repo, "CERT_MANAGER_MANIFEST_SHA256", "0" * 64)
    result = run(tmp_path, repo, ["tests/addon.sh", "cert-manager"])
    assert result.returncode != 0
    assert "checksum" in result.stderr
    assert not [c for c in calls(tmp_path) if c.startswith("kubectl apply")]


def test_addon_refuses_other_context(tmp_path):
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    result = run(tmp_path, repo, ["tests/addon.sh", "cert-manager"], context="aks-prod")
    assert result.returncode == 2
    assert REFUSAL in result.stderr
    assert not [c for c in calls(tmp_path) if c.startswith(("curl", "kubectl apply"))]


def test_addon_rejects_unknown_names(tmp_path):
    repo = make_repo(tmp_path)
    make_kubeconfig(repo)
    for args in ([], ["bogus"], ["cert-manager", "extra"]):
        result = run(tmp_path, repo, ["tests/addon.sh", *args])
        assert result.returncode == 64, (args, result.stderr)
        assert "usage:" in result.stderr

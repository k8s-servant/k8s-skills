"""Tests for the k8s-secret-guard hook: which shell commands it blocks, and its I/O."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "plugins/k8s-secret-guard/hooks/secret_guard.py"
_spec = importlib.util.spec_from_file_location("secret_guard", SCRIPT)
secret_guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(secret_guard)


@pytest.mark.parametrize(
    "command",
    [
        "kubectl get secret my-secret -n my-namespace -o yaml",
        "kubectl get secrets -A",
        "kubectl -n my-namespace get secrets",
        "kubectl --context my-context --namespace=my-namespace get secret",
        "kubectl get secret/my-secret -o jsonpath='{.data.password}'",
        "kubectl get all,secrets -n my-namespace",
        "kubectl get Secrets.v1 -n my-namespace",
        "kubectl describe secret my-secret",
        "kubectl edit secret my-secret",
        "kubectl get secret my-secret -o json | jq -r .data.token | base64 -d",
        "/usr/local/bin/kubectl get secret my-secret",
        "oc get secret my-secret",
        "kubectl get --raw /api/v1/namespaces/my-namespace/secrets/my-secret",
        "kubectl view-secret my-secret",
        "kubectl exec my-pod -n my-namespace -- env",
        "kubectl exec -it my-pod -- printenv",
        "kubectl exec my-pod -- cat /var/run/secrets/kubernetes.io/serviceaccount/token",
        "kubectl exec my-pod -- sh -c 'env | grep PASSWORD'",
        "kubectl get pods && kubectl get secret my-secret",
        "echo $(kubectl get secret my-secret -o yaml)",
        "echo `kubectl get secret my-secret`",
        "bash -c 'kubectl get secret my-secret'",
        "sudo kubectl get secret my-secret",
        "KUBECONFIG=my-kubeconfig kubectl get secret my-secret",
        "env KUBECONFIG=my-kubeconfig kubectl get secret my-secret",
        "watch kubectl get secrets",
        "timeout 10 kubectl get secret my-secret",
        "helm get values my-release -n my-namespace",
        "helm get manifest my-release",
        "helm get all my-release",
        "helm -n my-namespace get values my-release",
        "az keyvault secret show --vault-name my-vault -n my-secret",
        "aws secretsmanager get-secret-value --secret-id my-secret",
        "aws ssm get-parameter --name my-param --with-decryption",
        "gcloud secrets versions access latest --secret=my-secret",
        # Flags whose value the hook does not know must not hide the verb or the kind.
        "kubectl -v 6 get secret my-secret",
        "kubectl get -L app secret my-secret",
        "kubectl --cache-dir my-dir get secrets",
        "kubectl --profile cpu describe secret my-secret",
        # Wrapper flags with values must not hide the command.
        "sudo -u root kubectl get secret my-secret",
        "env -u MY_VAR kubectl get secret my-secret",
        "nice -n 5 kubectl get secret my-secret",
        "timeout -s KILL 10 kubectl get secret my-secret",
        "kubectl exec my-pod -- cat /proc/1/environ",
        # Cloud CLI global flags before the subcommand.
        "aws --profile my-profile --region eu-west-1 secretsmanager get-secret-value --secret-id x",
        "az --subscription my-sub keyvault secret show --vault-name my-vault -n my-secret",
        "gcloud --project my-project secrets versions access latest --secret=my-secret",
        # exec without --, copying a mounted Secret out, and oc extract.
        "kubectl exec my-pod env",
        "kubectl cp my-namespace/my-pod:/var/run/secrets/kubernetes.io/serviceaccount/token token",
        "oc extract secret/my-secret --to=-",
        # Shell keywords and eval in front of the command.
        "if true; then kubectl get secret my-secret; fi",
        "for i in 1; do kubectl get secret my-secret; done",
        "{ kubectl get secret my-secret; }",
        "eval 'kubectl get secret my-secret'",
        "kubectl exec my-pod -- sudo env",
        "helm --burst-limit 5 get values my-release",
        # Copying a directory that holds the Secret mounts, or a path that resolves to one.
        "kubectl cp my-pod:/var/run ./out",
        "kubectl cp my-pod:/ ./out",
        "kubectl cp my-pod:/tmp/../var/run/secrets ./out",
        "kubectl cp my-pod:var/run/secrets/kubernetes.io ./out",
        "kubectl get -- secret my-secret",
        "kubectl exec my-pod -- sh -c 'cat < /run/secrets/my-secret'",
        "kubectl exec my-pod -- sudo -u root env",
        "helm get --unknown-flag 1 values my-release",
        "kubectl cp my-pod:/var/run/secrets/my-dir:with-colon ./out",
    ],
)
def test_blocks_commands_that_read_secrets(command):
    assert secret_guard.reason(command) is not None


@pytest.mark.parametrize(
    "command",
    [
        "kubectl get pods -A",
        "kubectl get secretstores,externalsecrets -n my-namespace",
        "kubectl get clustersecretstores",
        "kubectl get secretproviderclasses -A",
        "kubectl describe externalsecret my-secret -n my-namespace",
        "kubectl get pod my-secret-reader -o yaml",
        "kubectl auth can-i get secrets -n my-namespace",
        "kubectl -v 6 auth can-i get secrets",
        "sudo -u root kubectl get pods",
        "aws --profile my-profile secretsmanager list-secrets",
        "kubectl cp my-namespace/my-pod:/tmp/my-app.log my-app.log",
        "kubectl exec my-pod -- ls /tmp",
        "kubectl exec my-pod -- cat /app/env",
        "kubectl get pods -n my-namespace > secret-report.txt",
        "kubectl logs my-pod -n my-namespace --tail=50",
        "kubectl exec my-pod -- cat /etc/my-app/config.yaml",
        "kubectl exec my-pod -- nslookup my-svc",
        "kubectl get events -n my-namespace --field-selector involvedObject.name=my-secret",
        "helm list -A",
        "helm status my-release",
        "helm history my-release",
        "az aks show -g my-resource-group -n my-cluster",
        "aws ssm get-parameter --name my-param",
        "grep -rn secret skills/",
        "env",
        "echo 'kubectl get secret is blocked'",
        "",
    ],
)
def test_allows_commands_that_do_not_read_secrets(command):
    assert secret_guard.reason(command) is None


def test_unparseable_command_mentioning_secrets_is_blocked():
    assert secret_guard.reason("kubectl get secret 'my-secret") is not None


@pytest.mark.parametrize(
    "command",
    [
        "kubectl exec my-pod -- env 'unbalanced",
        "helm get values my-release 'unbalanced",
        "kubectl exec my-pod -- cat /proc/1/environ 'unbalanced",
    ],
)
def test_unparseable_command_with_a_watched_word_is_blocked(command):
    assert secret_guard.reason(command) is not None


def test_unparseable_command_without_secrets_is_allowed():
    assert secret_guard.reason("echo 'unbalanced") is None


def run_hook(payload) -> subprocess.CompletedProcess:
    data = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(SCRIPT)], input=data, capture_output=True, text=True, check=False
    )


def test_hook_blocks_with_exit_2_and_tells_the_agent_why():
    result = run_hook(
        {"tool_name": "Bash", "tool_input": {"command": "kubectl get secret my-secret"}}
    )
    assert result.returncode == 2
    assert "k8s-secret-guard" in result.stderr
    assert "Secret" in result.stderr


def test_hook_allows_other_commands_silently():
    result = run_hook({"tool_name": "Bash", "tool_input": {"command": "kubectl get pods"}})
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_hook_ignores_other_tools():
    result = run_hook({"tool_name": "Read", "tool_input": {"file_path": "secrets.yaml"}})
    assert result.returncode == 0


def test_hook_reports_bad_input_without_blocking():
    result = run_hook("not json")
    assert result.returncode == 1
    assert "k8s-secret-guard" in result.stderr


def test_hook_blocks_when_nesting_is_too_deep_to_check():
    command = "eval " * 2000 + "kubectl get secret my-secret"
    result = run_hook({"tool_name": "Bash", "tool_input": {"command": command}})
    assert result.returncode == 2

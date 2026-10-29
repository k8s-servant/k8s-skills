#!/usr/bin/env python3
"""k8s-secret-guard: a Claude Code PreToolUse hook that blocks shell commands reading Secrets.

The k8s-skills tell the agent never to read Secrets. This hook is a second, best-effort
layer for agents that run with credentials allowed to read them: it refuses the common
ways to print a Secret (kubectl, helm, and the cloud secret stores) before the command
runs, and tells the agent why. A shell can always find another way, so the Kubernetes
RBAC of the agent's credentials stays the real guarantee.

Known gaps, among others: a script that prints a variable (`sh -c 'echo $PASSWORD'`),
a kind or Secrets API URL put together at run time (`kubectl get $KIND my-secret`), a
Secret named only inside a file (`kubectl get -f my-secret.yaml`), and a kubeconfig or
token copied out of a pod. The hook is kept small on purpose: a new bypass goes on this list, not into the
parser, since RBAC already covers it. It
errs towards blocking: `kubectl get configmap secrets` is refused too, since every word
after the verb is checked.

Input: the hook's JSON on stdin. Exit 0 lets the command run, exit 2 blocks it (stderr
goes to the agent), exit 1 reports a hook error to the user without blocking.
Standard library only, Python 3.9 or newer.
"""

import json
import posixpath
import re
import shlex
import sys

NAME = "k8s-secret-guard"
SEPARATORS = {";", "&", "&&", "|", "||", "|&", "(", ")", ";;", "!"}
REDIRECTS = {"<", ">", ">>", "<<", "<<<", ">&", "<&", "&>"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
KUBECTL = {"kubectl", "oc", "kubecolor"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
# Commands that run the rest of their arguments as another command.
WRAPPERS = {"sudo", "command", "nohup", "time", "watch", "xargs", "exec", "nice", "env"}
# Shell keywords that can stand in front of a command (`if ...; then kubectl ...; fi`).
KEYWORDS = {"if", "then", "else", "elif", "fi", "do", "done", "while", "until", "{", "}"}
# kubectl and helm flags that take a value as the next word.
VALUE_FLAGS = {
    "-n", "--namespace", "--context", "--kube-context", "--kubeconfig", "--cluster",
    "--user", "--server", "-s", "--token", "--as", "--as-group", "-l", "--selector",
    "--field-selector", "-o", "--output", "-c", "--container", "-f", "--filename",
    "--template", "--raw", "--request-timeout", "--tail", "--since", "--sort-by",
    "--chunk-size", "-p", "--revision",
}  # fmt: skip
# kubectl's own commands, so the verb is found even after a flag value the hook does not
# know (`kubectl -v 6 get ...`).
KUBECTL_VERBS = {
    "get", "describe", "edit", "exec", "view-secret", "auth", "logs", "events", "top",
    "explain", "api-resources", "api-versions", "config", "cluster-info", "version",
    "apply", "create", "delete", "replace", "patch", "label", "annotate", "set", "scale",
    "autoscale", "rollout", "expose", "run", "wait", "diff", "debug", "attach", "cp",
    "port-forward", "proxy", "drain", "cordon", "uncordon", "taint", "certificate",
    "kustomize", "plugin", "completion", "extract",
}  # fmt: skip
PROGRAMS = KUBECTL | SHELLS | {"helm", "az", "aws", "gcloud"}
SECRET_KINDS = {"secret", "secrets"}
SECRET_MOUNTS = ("/run/secrets", "/var/run/secrets")
HELM_SECRET_VIEWS = {"values", "manifest", "all", "hooks"}
# The Secrets API path, whatever sends the request (`kubectl proxy` plus `curl`).
SECRETS_API = re.compile(r"/api/v1/(?:watch/)?(?:namespaces/[^/\s]+/)?secrets(?![\w-])")
# Words that, in a command the hook cannot parse, are reason enough to block it.
WATCHED = re.compile(r"secret|environ|printenv|\benv\b|helm\s+get", re.IGNORECASE)


def reason(command: str) -> "str | None":
    """Return why `command` would read a Secret, or None if it would not."""
    return _check_line(command, remote=False)


def _check_line(command: str, remote: bool) -> "str | None":
    # Command substitution in backticks runs like any other command; split there too.
    text = command.replace("`", " ; ").replace("\n", " ; ")
    try:
        lexer = shlex.shlex(text, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        if WATCHED.search(command):
            return "the command could not be parsed and may read a Secret"
        return None
    for words in _segments(tokens):
        found = _check_words(words, remote)
        if found:
            return found
    return None


def _segments(tokens: list) -> list:
    """Split a token list into simple commands, dropping redirections and their targets."""
    segments, current, skip = [], [], False
    for token in tokens:
        if skip:
            skip = False
        elif token in SEPARATORS or token == "$":
            if current:
                segments.append(current)
            current = []
        elif token in REDIRECTS:
            skip = True
        else:
            current.append(token)
    if current:
        segments.append(current)
    return segments


def _program(word: str) -> str:
    name = word.rsplit("/", 1)[-1].lower()
    return name.removesuffix(".exe")


def _strip_wrappers(words: list) -> list:
    wrapped = False
    while words:
        name = _program(words[0])
        if ASSIGNMENT.match(words[0]) or words[0] in KEYWORDS:
            words = words[1:]
        elif name in WRAPPERS or name == "timeout":
            wrapped = True
            words = words[1:]
            while words and words[0].startswith("-"):
                words = words[1:]
            if name == "timeout" and words:
                words = words[1:]
        else:
            break
    # A wrapper flag's value (`sudo -u root`, `nice -n 5`) is still in front: skip ahead
    # to the first program the hook knows.
    if wrapped and words and _program(words[0]) not in PROGRAMS:
        for index, word in enumerate(words):
            if _program(word) in PROGRAMS:
                return words[index:]
    return words


def _check_words(words: list, remote: bool) -> "str | None":
    if any(SECRETS_API.search(word) for word in words):
        return "it calls the Secrets API"
    if remote:
        # `env` and `printenv` print the environment, also behind `sudo -u root` or `nohup`.
        if any(w in {"env", "printenv"} or w.endswith(("bin/env", "bin/printenv")) for w in words):
            return "it prints a container's environment, which holds Secret values"
        if any("/run/secrets" in word for word in words):
            return "it reads a Secret mounted into a container"
        if any(word.endswith("/environ") for word in words):
            return "it reads a process environment, which holds Secret values"
    words = _strip_wrappers(words)
    if not words:
        return None
    program, args = _program(words[0]), words[1:]
    if program in SHELLS:
        script = _shell_script(args)
        return _check_line(script, remote) if script is not None else None
    if program == "eval":
        return _check_line(" ".join(args), remote)
    if program in KUBECTL:
        return _check_kubectl(args)
    if program == "helm":
        positional, _ = _parse(args)
        # `get` need not come first: an unknown flag's value can stand before it.
        if "get" in positional:
            for view in positional[positional.index("get") + 1 :]:
                if view in HELM_SECRET_VIEWS:
                    return f"helm get {view} prints values from the release's Secret"
    # Global flags and their values can come before the subcommand
    # (`aws --profile my-profile secretsmanager ...`), so match the words in order.
    plain = [word for word in args if not word.startswith("-")]
    if program == "az" and any(
        _in_order(["keyvault", "secret", action], plain)
        for action in ("show", "download", "backup")
    ):
        return "it reads a secret from Azure Key Vault"
    if program == "aws":
        if any(
            _in_order(["secretsmanager", action], plain)
            for action in ("get-secret-value", "batch-get-secret-value")
        ):
            return "it reads a secret from AWS Secrets Manager"
        if "ssm" in plain and "--with-decryption" in args:
            return "it decrypts a SecureString from AWS Systems Manager"
    if program == "gcloud" and _in_order(["secrets", "versions", "access"], plain):
        return "it reads a secret from Google Secret Manager"
    return None


def _in_order(wanted: list, words: list) -> bool:
    """Whether `wanted` appears in `words` in this order, other words allowed in between."""
    rest = iter(words)
    return all(word in rest for word in wanted)


def _shell_script(args: list) -> "str | None":
    """The script a shell runs with -c, if any."""
    for index, word in enumerate(args):
        if word.startswith("-") and not word.startswith("--") and "c" in word[1:]:
            return args[index + 1] if index + 1 < len(args) else None
    return None


def _parse(args: list) -> tuple:
    """Split kubectl or helm arguments into positional words and flag values."""
    positional, values, index = [], {}, 0
    while index < len(args):
        word = args[index]
        if word == "--":
            # kubectl reads words after `--` as positional too (`get -- secret`); exec's
            # remote command is taken from the raw arguments instead.
            index += 1
            continue
        if word.startswith("--") and "=" in word:
            flag, value = word.split("=", 1)
            values[flag] = value
        elif word in VALUE_FLAGS:
            values[word] = args[index + 1] if index + 1 < len(args) else ""
            index += 1
        elif not word.startswith("-"):
            positional.append(word)
        index += 1
    return positional, values


def _check_kubectl(args: list) -> "str | None":
    positional, values = _parse(args)
    if "/secrets" in values.get("--raw", ""):
        return "it reads Secrets through the raw API"
    at = next((i for i, word in enumerate(positional) if word in KUBECTL_VERBS), 0)
    verb = positional[at] if positional else ""
    if verb in {"get", "describe", "edit", "extract"}:
        # Every word after the verb, since an unknown flag's value can come before the kind.
        for word in positional[at + 1 :]:
            for kind in word.split(","):
                if kind.split("/")[0].split(".")[0].lower() in SECRET_KINDS:
                    return f"kubectl {verb} on a Secret"
    if verb == "view-secret":
        return "kubectl view-secret prints a Secret"
    if verb == "cp" and any(_copies_secret_mount(word) for word in positional):
        return "it copies a Secret mounted into a container"
    if verb == "exec":
        # `exec POD -- CMD`, or the old form without `--`: everything after the pod name.
        remote = args[args.index("--") + 1 :] if "--" in args else positional[at + 2 :]
        if remote:
            return _check_words(remote, remote=True)
    return None


def _copies_secret_mount(word: str) -> bool:
    """Whether a `kubectl cp` pod path is, holds or lies under a Secret mount."""
    if any(mount in word for mount in SECRET_MOUNTS):
        return True
    # kubectl splits `pod:path` at the first colon; the path may hold more.
    _, colon, path = word.partition(":")
    if not colon:
        return False
    path = posixpath.normpath("/" + path.lstrip("/"))
    under = path.rstrip("/") + "/"
    return any(
        path == mount or path.startswith(mount + "/") or mount.startswith(under)
        for mount in SECRET_MOUNTS
    )


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        tool = payload.get("tool_name")
        command = (payload.get("tool_input") or {}).get("command") or ""
    except (ValueError, AttributeError) as exc:
        print(f"{NAME}: could not read the hook input ({exc}); not blocking", file=sys.stderr)
        return 1
    if tool != "Bash":
        return 0
    try:
        why = reason(command)
    except Exception as exc:  # noqa: BLE001 - even RecursionError: decide from the words
        if not WATCHED.search(command):
            print(f"{NAME}: could not check the command ({exc!r}); not blocking", file=sys.stderr)
            return 1
        why = "the command could not be checked and may read a Secret"
    if why is None:
        return 0
    print(
        f"Blocked by {NAME}: {why}. The k8s-skills never read Secret values. Continue "
        "without it; if the value matters, ask the user to check it themselves.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""k8s-secret-guard: a Claude Code PreToolUse hook that blocks shell commands reading Secrets.

The k8s-skills tell the agent never to read Secrets. This hook is a second, best-effort
layer for agents that run with credentials allowed to read them: it refuses the common
ways to print a Secret (kubectl, helm, and the cloud secret stores) before the command
runs, and tells the agent why. A shell can always find another way, so the Kubernetes
RBAC of the agent's credentials stays the real guarantee.

Input: the hook's JSON on stdin. Exit 0 lets the command run, exit 2 blocks it (stderr
goes to the agent), exit 1 reports a hook error to the user without blocking.
Standard library only, Python 3.9 or newer.
"""

import json
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
# kubectl and helm flags that take a value as the next word.
VALUE_FLAGS = {
    "-n", "--namespace", "--context", "--kube-context", "--kubeconfig", "--cluster",
    "--user", "--server", "-s", "--token", "--as", "--as-group", "-l", "--selector",
    "--field-selector", "-o", "--output", "-c", "--container", "-f", "--filename",
    "--template", "--raw", "--request-timeout", "--tail", "--since", "--sort-by",
    "--chunk-size", "-p", "--revision",
}  # fmt: skip
SECRET_KINDS = {"secret", "secrets"}
HELM_SECRET_VIEWS = {"values", "manifest", "all", "hooks"}


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
        if re.search(r"secret", command, re.IGNORECASE):
            return "the command could not be parsed and mentions secrets"
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
    while words:
        name = _program(words[0])
        if ASSIGNMENT.match(words[0]):
            words = words[1:]
        elif name in WRAPPERS or name == "timeout":
            words = words[1:]
            while words and words[0].startswith("-"):
                words = words[1:]
            if name == "timeout" and words:
                words = words[1:]
        else:
            break
    return words


def _check_words(words: list, remote: bool) -> "str | None":
    if remote:
        if _program(words[0]) in {"env", "printenv"}:
            return "it prints a container's environment, which holds Secret values"
        if any("/run/secrets" in word for word in words):
            return "it reads a Secret mounted into a container"
    words = _strip_wrappers(words)
    if not words:
        return None
    program, args = _program(words[0]), words[1:]
    if program in SHELLS:
        script = _shell_script(args)
        return _check_line(script, remote) if script is not None else None
    if program in KUBECTL:
        return _check_kubectl(args)
    if program == "helm":
        positional, _ = _parse(args)
        if positional[:1] == ["get"] and positional[1:2] and positional[1] in HELM_SECRET_VIEWS:
            return "helm get " + positional[1] + " prints values from the release's Secret"
    plain = [word for word in args if not word.startswith("-")]
    if (
        program == "az"
        and plain[:2] == ["keyvault", "secret"]
        and plain[2:3] in (["show"], ["download"], ["backup"])
    ):
        return "it reads a secret from Azure Key Vault"
    if program == "aws":
        if plain[:2] in (
            ["secretsmanager", "get-secret-value"],
            ["secretsmanager", "batch-get-secret-value"],
        ):
            return "it reads a secret from AWS Secrets Manager"
        if plain[:1] == ["ssm"] and "--with-decryption" in args:
            return "it decrypts a SecureString from AWS Systems Manager"
    if program == "gcloud" and plain[:3] == ["secrets", "versions", "access"]:
        return "it reads a secret from Google Secret Manager"
    return None


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
            break
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
    verb = positional[0] if positional else ""
    if verb in {"get", "describe", "edit"} and len(positional) > 1:
        for kind in positional[1].split(","):
            if kind.split("/")[0].split(".")[0].lower() in SECRET_KINDS:
                return "kubectl " + verb + " on a Secret"
    if verb == "view-secret":
        return "kubectl view-secret prints a Secret"
    if verb == "exec" and "--" in args:
        remote = args[args.index("--") + 1 :]
        if remote:
            return _check_words(remote, remote=True)
    return None


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
    why = reason(command)
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

"""Tests for the command allow-list check: the rules that keep skills read-only."""

from pathlib import Path

import pytest

from tools.skillcheck.commands import (
    MARKER,
    check_commands,
    extract_blocks,
    load_allowlist,
)

FRONTMATTER = (
    "---\nname: k8s-demo-skill\ndescription: Use when testing.\nlicense: Apache-2.0\n"
    'metadata:\n  verified-with: kind\n  verified-on: "2026-10-23"\n---\n'
)


def run(
    root: Path,
    body: str = "",
    refs: dict[str, str] | None = None,
    scripts: dict[str, str] | None = None,
) -> list:
    """Build skills/k8s-demo-skill under root and return the command findings."""
    skill_dir = root / "skills" / "k8s-demo-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(FRONTMATTER + body, encoding="utf-8")
    for sub, files in (("references", refs or {}), ("scripts", scripts or {})):
        for name, text in files.items():
            target = skill_dir / sub / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
    return check_commands(skill_dir, load_allowlist())


def messages(findings: list) -> list[str]:
    return [f.message for f in findings]


def bash(*lines: str) -> str:
    return "```bash\n" + "\n".join(lines) + "\n```\n"


def test_allowed_kubectl_passes(tmp_path):
    assert run(tmp_path, bash("kubectl get pods -n my-namespace -o wide")) == []


def test_flag_before_subcommand_passes(tmp_path):
    assert run(tmp_path, bash("kubectl -n my-namespace get pods")) == []


def test_two_word_subcommand(tmp_path):
    assert run(tmp_path, bash("kubectl rollout status deploy/my-app")) == []
    found = run(tmp_path / "b", bash("kubectl rollout undo deploy/my-app"))
    assert any("not on the allow-list" in m for m in messages(found))


def test_write_verb_fails(tmp_path):
    found = run(tmp_path, bash("kubectl delete pod my-app-1"))
    assert any("not on the allow-list" in m and "kubectl delete" in m for m in messages(found))


def test_unknown_program_fails(tmp_path):
    found = run(tmp_path, bash("rm -rf /tmp/x", "helm list"))
    assert len(found) == 2


def test_untyped_block_is_an_error(tmp_path):
    found = run(tmp_path, "```\nkubectl get pods\n```\n")
    assert messages(found) == ["fenced block needs a language"]
    assert found[0].line == 9


def test_prompt_prefix_is_stripped(tmp_path):
    found = run(tmp_path, bash("$ kubectl delete pod x"))
    assert any("not on the allow-list" in m for m in messages(found))
    assert run(tmp_path / "b", bash("$ kubectl get pods")) == []


def test_continuation_is_joined(tmp_path):
    found = run(tmp_path, bash("kubectl get pods \\", "  --as=admin"))
    assert messages(found) == ["global flag not allowed"]
    assert found[0].line == 10


@pytest.mark.parametrize(
    "line",
    [
        "kubectl get pods; rm x",
        "kubectl get pods;rm x",
        "kubectl get pods && rm x",
        "kubectl get pods&&rm x",
        "kubectl get pods || rm x",
        "kubectl get pods ||rm x",
        "kubectl get pods > out.txt",
        "kubectl get pods >out.txt",
        "kubectl get pods >> out.txt",
        "kubectl get pods < in.txt",
        "kubectl get pods $(kubectl get nodes)",
        "kubectl get `echo pods`",
        'kubectl get "$(echo pods)"',
        'kubectl get "`echo pods`"',
        "kubectl get pods &",
        "kubectl get pods <(echo x)",
        "kubectl get $RESOURCE",
        "kubectl get pods${IFS}x",
        'kubectl get "$RESOURCE"',
    ],
)
def test_shell_control_is_rejected(tmp_path, line):
    assert "shell control not allowed" in messages(run(tmp_path, bash(line)))


def test_quoted_control_characters_are_fine(tmp_path):
    line = "kubectl get pods -o jsonpath='{.items[*].metadata.name};&&>'"
    assert run(tmp_path, bash(line)) == []
    assert run(tmp_path / "b", bash("kubectl get pods | grep -E 'a|b'")) == []


def test_single_quoted_dollar_is_fine(tmp_path):
    assert run(tmp_path, bash("kubectl get pods | jq '$ENV.x'")) == []


def test_unbalanced_quote_is_a_finding_not_a_crash(tmp_path):
    assert messages(run(tmp_path, bash("kubectl get pods -l 'app=x"))) == ["cannot parse command"]


def test_pipe_to_filter_passes(tmp_path):
    assert run(tmp_path, bash("kubectl get pods -A | grep -v Running")) == []
    assert run(tmp_path / "b", bash("kubectl get pods -A|grep -v Running|wc -l")) == []


def test_pipe_to_other_command_fails(tmp_path):
    found = run(tmp_path, bash("kubectl get pods -o name | xargs kubectl delete"))
    assert any("filter" in m for m in messages(found))


def test_fix_block_is_exempt_but_needs_undo(tmp_path):
    body = f"{MARKER}\n\n```bash\nkubectl delete pod my-app-1\n```\n"
    found = run(tmp_path, body)
    assert messages(found) == ["proposed fix needs an '# Undo:' line"]
    body = (
        f"{MARKER}\n```bash\n# Undo: kubectl apply -f old.yaml\nkubectl delete pod my-app-1\n```\n"
    )
    assert run(tmp_path / "b", body) == []


def test_marker_must_be_exact(tmp_path):
    near = "> Proposed fix: review before running."
    body = f"{near}\n```bash\nkubectl delete pod my-app-1\n```\n"
    assert any("not on the allow-list" in m for m in messages(run(tmp_path, body)))
    body = (
        "> proposed fix: review before running. The agent does not run this.\n```bash\nrm x\n```\n"
    )
    assert run(tmp_path / "b", body)


def test_marker_must_be_directly_above_the_fence(tmp_path):
    body = f"{MARKER}\n\nSome prose.\n\n```bash\nkubectl delete pod x\n```\n"
    assert any("not on the allow-list" in m for m in messages(run(tmp_path, body)))


@pytest.mark.parametrize(
    "line",
    [
        "kubectl get secrets",
        "kubectl get secret",
        "kubectl get Secrets -A",
        "kubectl describe secret/db-creds",
        "kubectl get secrets.v1",
        "kubectl get pods,secrets",
        "kubectl get secret db-creds -o yaml",
        "kubectl get --raw /api/v1/namespaces/my-namespace/secrets",
        "kubectl get {pods,secrets}",
    ],
)
def test_secret_access_fails_everywhere(tmp_path, line):
    found = run(tmp_path, bash(line))
    assert "Secret access is not allowed" in messages(found)
    body = f"{MARKER}\n```bash\n# Undo: kubectl apply -f a.yaml\n{line}\n```\n"
    assert "Secret access is not allowed" in messages(run(tmp_path / "fix", body))


def test_secret_like_words_pass(tmp_path):
    assert run(tmp_path, bash("kubectl get externalsecrets", "kubectl get sealedsecrets")) == []


def test_forbidden_flags(tmp_path):
    for i, line in enumerate(
        [
            "kubectl get pods --server https://example.com",
            "kubectl get pods --server=https://example.com",
            "kubectl get pods -s https://example.com",
            "kubectl get pods -shttps://example.com",
            "kubectl get pods --token=abc",
            "kubectl get pods --kubeconfig /tmp/x",
            "kubectl --context other get pods",
            "kubectl get pods --as-group=x",
        ]
    ):
        found = run(tmp_path / str(i), bash(line))
        assert "global flag not allowed" in messages(found), line


def test_yaml_block_is_ignored(tmp_path):
    assert run(tmp_path, "```yaml\nkind: Pod\nname: my-app\n```\n") == []


def test_comments_and_blank_lines_are_skipped(tmp_path):
    assert run(tmp_path, bash("# a comment", "", "kubectl get pods")) == []


def test_references_are_checked_without_frontmatter(tmp_path):
    found = run(tmp_path, refs={"deep.md": bash("kubectl delete pod x")})
    assert found[0].path == Path("skills/k8s-demo-skill/references/deep.md")
    assert found[0].line == 2


def test_scripts_are_checked(tmp_path):
    found = run(
        tmp_path, scripts={"probe.sh": "#!/bin/sh\nkubectl get pods\nkubectl delete pod x\n"}
    )
    assert len(found) == 1
    assert found[0].path == Path("skills/k8s-demo-skill/scripts/probe.sh")
    assert found[0].line == 3


def test_skill_md_line_numbers_are_file_lines(tmp_path):
    found = run(tmp_path, "text\n\n" + bash("kubectl get pods", "kubectl delete pod x"))
    assert found[0].path == Path("skills/k8s-demo-skill/SKILL.md")
    assert found[0].line == 13


def test_extract_blocks():
    md = "a\n```bash\nx\ny\n```\n~~~sh\nz\n~~~\n```\nq\n```\n"
    blocks = extract_blocks(md)
    assert [(b.lang, b.start_line, b.lines) for b in blocks] == [
        ("bash", 2, ["x", "y"]),
        ("sh", 6, ["z"]),
        (None, 9, ["q"]),
    ]
    assert not any(b.is_fix for b in blocks)


def test_extract_blocks_marks_fix():
    blocks = extract_blocks(f"{MARKER}\n\n```bash\nx\n```\n")
    assert blocks[0].is_fix


def test_marker_matches_constraint():
    assert MARKER == "> Proposed fix: review before running. The agent does not run this."


def fails(tmp_path, body, expect=None, **kw):
    """Run a probe in its own folder; return True if a (matching) finding appears."""
    found = messages(run(tmp_path, body, **kw))
    return bool(found) if expect is None else any(expect in m for m in found)


@pytest.mark.parametrize(
    ("line", "expect"),
    [
        ("kubectl rollout -n status undo deploy/my-app", "not on the allow-list"),
        ("kubectl auth -n can-i reconcile -f rbac.yaml", "not on the allow-list"),
        ("kubectl --cache-dir get delete pod x", "global flag not allowed"),
        ("kubectl get pods -As https://evil.example.com", "global flag not allowed"),
        ("kubectl get pods {--as=admin,}", "shell control"),
        ("kubectl get pods $'--as=admin'", "shell control"),
        ('kubectl get pods $"--server=https://evil.example.com"', "shell control"),
        ("kubectl get $'\\x73ecrets'", "shell control"),
        ("kubectl get se''crets", "Secret access"),
        ('kubectl get "se"crets', "Secret access"),
        ("kubectl get sec\\rets", "shell control"),
        ("kubectl get --raw /api/v1/namespaces/x/%73ecrets", "percent-encoding"),
        ("kubectl get --raw=/api/v1/namespaces/x/%73ecrets", "percent-encoding"),
        ("kubectl get pods --profile=cpu --profile-output=/tmp/x", "global flag"),
        ("kubectl get pods --client-certificate=/tmp/c", "global flag"),
        ("kubectl get pods --tls-server-name=x", "global flag"),
        ("kubectl get pods --certificate-authority=/tmp/c", "global flag"),
        ("kubectl get pods -fs https://x", "global flag"),
        ("kubectl get pods -Z", "flag not allowed"),
        ("kubectl -v 6 -s https://x get pods", "global flag"),
        ("kubectl get pods | sed -n p", "allow-listed filter"),
        ("kubectl get pods | awk '{print $1}'", "allow-listed filter"),
        ("kubectl get pods | sort --compress-program=sh", "flag not allowed for sort"),
        ("kubectl get pods | sort -o out.txt", "flag not allowed for sort"),
        ("kubectl get pods | tail -f", "flag not allowed for tail"),
        ("kubectl get pods | tail --follow", "flag not allowed for tail"),
        ("kubectl get pods | head -qn 1", "flag not allowed for head"),
        ("kubectl get pods | grep -f /etc/passwd", "flag not allowed for grep"),
        ("kubectl get pods | grep -r x", "flag not allowed for grep"),
        ("kubectl get pods | grep x /etc/passwd", "file argument"),
        ("kubectl get pods | grep -e x /etc/passwd", "file argument"),
        ("kubectl get pods | jq --rawfile x /etc/passwd .", "flag not allowed for jq"),
        ("kubectl get pods | jq . /etc/passwd", "file argument"),
        ("kubectl get pods -o yaml | yq -i .a f.yaml", "flag not allowed for yq"),
        ("kubectl get pods | uniq in.txt out.txt", "file argument"),
        ("kubectl get pods | sort out.txt", "file argument"),
        ("kubectl get pods | wc -l extra", "file argument"),
        ("kubectl get pods | cut -d, -f1 -- x", "flag not allowed for cut"),
    ],
)
def test_review_bypass_probes(tmp_path, line, expect):
    assert fails(tmp_path, bash(line), expect), line


@pytest.mark.parametrize(
    "line",
    [
        "kubectl -n my-namespace get pods",
        "kubectl --namespace my-namespace get pods",
        "kubectl --namespace=my-namespace get pods -A -ojson",
        "kubectl logs my-app -n my-namespace --since 1h --tail=20 -f -c main",
        "kubectl get pods --request-timeout=5s -v 4",
        "kubectl get pods -A | grep -v -E 'Running|Completed' | wc -l",
        "kubectl get pods | grep -A 2 -i error",
        "kubectl get pods -o json | jq -r '.items[].metadata.name'",
        "kubectl get pods -o json | jq --arg n x '.items[] | select(.metadata.name == $n)'",
        "kubectl get pods -o yaml | yq e '.items[0]'",
        "kubectl get pods -o yaml | yq -o json '.a'",
        "kubectl get pods | sort -k 2 -r | uniq -c | head -n 5",
        "kubectl get pods | head -5 | tail -n +2 | column -t -s ' '",
        "kubectl get pods | cut -d ' ' -f 1",
        "kubectl get pods | grep -e Running -e Pending",
        "kubectl get pods | sort -nr",
    ],
)
def test_legitimate_commands_pass(tmp_path, line):
    assert run(tmp_path, bash(line)) == [], line


def test_escaped_backslash_is_not_a_continuation(tmp_path):
    found = run(tmp_path, bash("kubectl get pods \\\\", "kubectl delete pod x"))
    assert any("kubectl delete" in m for m in messages(found))


def test_odd_backslashes_continue(tmp_path):
    assert run(tmp_path, bash("kubectl get pods \\", "  -o wide")) == []


def test_blockquote_fence_is_scanned(tmp_path):
    body = "> ```bash\n> kubectl delete pod x\n> ```\n"
    found = run(tmp_path, body)
    assert any("not on the allow-list" in m for m in messages(found))
    assert found[0].line == 10


def test_list_item_fence_is_scanned(tmp_path):
    assert fails(tmp_path, "- ```bash\n  kubectl delete pod x\n  ```\n")
    assert fails(tmp_path / "b", "- step\n\n  ```bash\n  kubectl delete pod x\n  ```\n")


@pytest.mark.parametrize("info", ["bash{.copy}", "{bash}", "{.bash}", "BASH", "bash title=x"])
def test_language_attributes_do_not_hide_a_block(tmp_path, info):
    assert fails(tmp_path, f"```{info}\nkubectl delete pod x\n```\n"), info


@pytest.mark.parametrize("lang", ["shell-session", "text", "yaml", "json", "{.x}"])
def test_commands_hidden_in_other_languages_are_checked(tmp_path, lang):
    assert fails(tmp_path, f"```{lang}\nkubectl delete pod x\n```\n", "not on the allow-list")


def test_example_output_in_text_block_is_fine(tmp_path):
    out = "```text\nNAME READY STATUS\nmy-app-1 1/1 Running\n```\n"
    assert run(tmp_path, out) == []


def test_console_output_lines_are_not_commands(tmp_path):
    body = "```console\n$ kubectl get pods\nNAME READY\nmy-app 1/1\nrm -rf x\n```\n"
    assert run(tmp_path, body) == []
    assert fails(tmp_path / "b", "```console\n$ kubectl delete pod x\nok\n```\n")
    assert fails(tmp_path / "c", "```console\nkubectl delete pod x\n```\n")


def test_nested_scripts_and_references_are_checked(tmp_path):
    found = run(tmp_path, scripts={"lib/x.sh": "kubectl delete pod x\n"})
    assert found[0].path == Path("skills/k8s-demo-skill/scripts/lib/x.sh")
    found = run(tmp_path / "b", refs={"deep/x.md": bash("kubectl delete pod x")})
    assert found


def test_non_utf8_files_do_not_crash(tmp_path):
    root = tmp_path / "skills" / "k8s-demo-skill"
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_bytes(b"\xff\xfe---\n")
    (root / "references" / "x.md").write_bytes(b"\xff\xfe\n```bash\nkubectl delete pod x\n```\n")
    found = check_commands(root, load_allowlist())
    assert [m for m in messages(found)].count("file is not valid UTF-8") == 2
    assert any("not on the allow-list" in m for m in messages(found))


def test_undo_line_is_scanned_for_secrets(tmp_path):
    body = f"{MARKER}\n```bash\n# Undo: kubectl get secret x -o yaml\nkubectl delete pod x\n```\n"
    assert "Secret access is not allowed" in messages(run(tmp_path, body))


def test_indented_marker_does_not_mark_a_fix(tmp_path):
    body = f"    {MARKER}\n```bash\n# Undo: x\nkubectl delete pod x\n```\n"
    assert fails(tmp_path, body, "not on the allow-list")


def test_marker_with_trailing_whitespace_still_marks_a_fix(tmp_path):
    body = f"{MARKER}   \n```bash\n# Undo: x\nkubectl delete pod x\n```\n"
    assert run(tmp_path, body) == []


@pytest.mark.parametrize(
    "line",
    [
        "kubectl get $'\\x73ecrets'",
        "kubectl get se''crets",
        'kubectl get "se"crets',
        "kubectl get sec\\rets",
        "kubectl get {se,}crets",
    ],
)
def test_obfuscated_secret_access_fails_in_fix_blocks(tmp_path, line):
    body = f"{MARKER}\n```bash\n# Undo: kubectl apply -f a.yaml\n{line}\n```\n"
    assert fails(tmp_path, body), line


def test_comment_does_not_continue_onto_the_next_line(tmp_path):
    found = run(tmp_path, bash("kubectl get pods # \\", "kubectl delete pod x"))
    assert any("kubectl delete" in m for m in messages(found))


def test_hash_inside_a_word_or_quotes_is_not_a_comment(tmp_path):
    assert run(tmp_path, bash("kubectl get pods | grep '#' | grep a#b")) == []


def test_text_block_continuation_does_not_hide_a_command(tmp_path):
    body = "```text\nsome output \\\nkubectl delete pod x\n```\n"
    assert fails(tmp_path, body, "not on the allow-list")


def test_console_output_continuation_does_not_hide_a_command(tmp_path):
    body = "```console\n$ kubectl get pods\nNAME READY \\\n$ kubectl delete pod x\n```\n"
    assert fails(tmp_path, body, "not on the allow-list")


def test_console_continuation_of_a_prompted_command_still_joins(tmp_path):
    assert run(tmp_path, "```console\n$ kubectl get pods \\\n  -o wide\nNAME\n```\n") == []


@pytest.mark.parametrize("closer", ["- ```", "> ```", "    ```", "1. ```"])
def test_lookalike_closing_fences_do_not_end_a_block(tmp_path, closer):
    body = f"```bash\n{closer}\nkubectl delete pod x\n"
    assert fails(tmp_path, body, "not on the allow-list"), closer


def test_closing_fence_may_be_indented_up_to_three_spaces(tmp_path):
    body = "```bash\nkubectl get pods\n   ```\n\nplain text\n"
    assert run(tmp_path, body) == []


def test_quoted_block_ends_when_the_quote_does(tmp_path):
    body = "> ```bash\n> kubectl get pods\n\nkubectl delete pod x\n"
    assert fails(tmp_path, body, "not on the allow-list")


def test_fix_block_rejects_expansion_and_concatenation(tmp_path):
    body = f'{MARKER}\n```bash\n# Undo: kubectl rollout undo deploy/x\nR=secre; kubectl get "$R"ts\n```\n'
    assert "shell control not allowed" in messages(run(tmp_path, body))


def test_fix_block_rejects_pipe_into_non_filter(tmp_path):
    body = f"{MARKER}\n```bash\n# Undo: x\necho c2VjcmV0cw== | base64 -d | xargs kubectl get\n```\n"
    assert any("allow-listed filter" in m for m in messages(run(tmp_path, body)))


@pytest.mark.parametrize(
    "cmd",
    [
        "kubectl delete pod my-app-1 && kubectl get pods",
        "kubectl delete pod $NAME",
        "kubectl delete pod $(kubectl get pods -o name)",
        "kubectl delete pod my-app-1 > out.txt",
    ],
)
def test_fix_block_keeps_shell_rules(tmp_path, cmd):
    body = f"{MARKER}\n```bash\n# Undo: kubectl apply -f a.yaml\n{cmd}\n```\n"
    assert "shell control not allowed" in messages(run(tmp_path, body)), cmd


def test_fix_block_plain_commands_and_filters_are_fine(tmp_path):
    body = (
        f"{MARKER}\n```bash\n# Undo: kubectl scale deploy/my-app --replicas=3\n"
        "kubectl scale deploy/my-app --replicas=0\n"
        "kubectl get pods | grep my-app\n```\n"
    )
    assert run(tmp_path, body) == []


def test_quoted_and_prompted_commands_in_text_blocks(tmp_path):
    assert fails(tmp_path, '```text\n"kubectl" delete pod x\n```\n', "not on the allow-list")
    assert fails(
        tmp_path / "b", "```text\nuser@host:~$ kubectl delete pod x\n```\n", "kubectl delete"
    )
    assert fails(tmp_path / "c", "```text\nkub''ectl delete pod x\n```\n", "kubectl delete")


def test_indented_code_block_is_scanned(tmp_path):
    assert fails(tmp_path, "para\n\n    kubectl delete pod x\n", "not on the allow-list")


def test_html_pre_and_code_blocks_are_scanned(tmp_path):
    assert fails(tmp_path, "<pre>\nkubectl delete pod x\n</pre>\n", "not on the allow-list")
    assert fails(tmp_path / "b", "<pre><code>kubectl delete pod x</code></pre>\n")


def test_prose_commands_and_secrets_are_checked(tmp_path):
    assert fails(tmp_path, "Run kubectl get secrets to see them.\n", "Secret access")
    assert run(tmp_path / "b", "Plain prose without the tool name.\n") == []
    assert run(tmp_path / "c", "Run `kubectl get pods -A` first.\n") == []


def test_frontmatter_is_not_scanned_as_prose(tmp_path):
    skill_dir = tmp_path / "skills" / "k8s-demo-skill"
    skill_dir.mkdir(parents=True)
    text = FRONTMATTER.replace("Use when testing.", "Use when kubectl delete is mentioned.")
    (skill_dir / "SKILL.md").write_text(text + "body\n")
    assert check_commands(skill_dir, load_allowlist()) == []

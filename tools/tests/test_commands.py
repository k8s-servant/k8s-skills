"""Tests for the command allow-list check: the rules that keep skills read-only."""

from pathlib import Path

import pytest

from tools.skillcheck.commands import (
    ASK_MARKER,
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
        ("kubectl get pods -fs https://x", "flag would block or read local files"),
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
        "kubectl logs my-app -n my-namespace --since 1h --tail=20 -c main",
        "kubectl get pods -o go-template='{{.metadata.name}}'",
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
        "kubectl get se''crets",
        'kubectl get "se"crets',
        "kubectl get sec\\rets",
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


def test_html_pre_and_code_blocks_are_scanned(tmp_path):
    assert fails(tmp_path, "<pre>\nkubectl delete pod x\n</pre>\n", "not on the allow-list")
    assert fails(tmp_path / "b", "<pre><code>kubectl delete pod x</code></pre>\n")


def test_frontmatter_is_not_scanned_as_prose(tmp_path):
    skill_dir = tmp_path / "skills" / "k8s-demo-skill"
    skill_dir.mkdir(parents=True)
    text = FRONTMATTER.replace("Use when testing.", "Use when kubectl delete is mentioned.")
    (skill_dir / "SKILL.md").write_text(text + "body\n")
    assert check_commands(skill_dir, load_allowlist()) == []


def test_fix_block_allows_shell_features(tmp_path):
    body = (
        f"{MARKER}\n```bash\n# Undo: kubectl scale deploy/my-app --replicas=3\n"
        "kubectl scale deploy/my-app --replicas=0 && kubectl get pods | grep my-app\n"
        "NS=my-namespace; kubectl delete pod $NAME -n $NS > /dev/null\n```\n"
    )
    assert run(tmp_path, body) == []


def test_fix_block_still_needs_undo_and_no_secrets(tmp_path):
    body = f"{MARKER}\n```bash\nkubectl delete pod x && kubectl get secrets\n```\n"
    found = messages(run(tmp_path, body))
    assert "proposed fix needs an '# Undo:' line" in found
    assert "Secret access is not allowed" in found


def test_indented_code_block_needs_a_language(tmp_path):
    found = run(tmp_path, "para\n\n    kubectl delete pod x\n")
    assert messages(found) == ["fenced block needs a language"]


def test_prose_mention_is_fine(tmp_path):
    body = "## Using kubectl\n\nThe kubectl guard refuses writes.\n\n| kubectl get pods | lists |\n"
    assert run(tmp_path, body) == []


def test_inline_code_command_is_checked(tmp_path):
    found = run(tmp_path, "To remove it run `kubectl delete pod x` now.\n")
    assert any("not on the allow-list" in m for m in messages(found))
    assert run(tmp_path / "b", "Run `kubectl get pods -A` first.\n") == []
    assert "Secret access is not allowed" in messages(
        run(tmp_path / "c", "Look at `kubectl get secrets`.\n")
    )


def test_table_with_inline_code_command_is_checked(tmp_path):
    body = "| step | command |\n| --- | --- |\n| 1 | `kubectl delete pod x` |\n"
    assert fails(tmp_path, body, "not on the allow-list")


def test_paragraph_line_starting_with_a_command_is_checked(tmp_path):
    assert fails(tmp_path, "Intro.\nkubectl delete pod x\n", "not on the allow-list")


# Round-3 review probes: fences that a hand-written parser got wrong.
@pytest.mark.parametrize(
    "body",
    [
        "- Do this:\n\n    ```bash\n    helm uninstall my-app\n    ```\n",
        "- a\n  - b\n    - ```bash\n      rm -rf /var/lib/x\n      ```\n",
        "1. Step\n\n     ```bash\n     helm uninstall my-app\n     ```\n",
        "   ```bash\n    ```\nhelm uninstall my-app\n",
        " ```bash\n    ```\nkubectl delete pod x\n",
        "> ```bash\n> > ```\n> helm uninstall my-app\n\nok\n",
        "\t```bash\nhelm uninstall y\n```\n",
        "````bash\n```\nhelm uninstall y\n````\n",
        "~~~bash `x`\nkubectl delete pod x\n~~~\n",
    ],
)
def test_nested_and_odd_fences_are_found(tmp_path, body):
    assert fails(tmp_path, body), body


def test_fix_marker_must_sit_directly_above_a_top_level_fence(tmp_path):
    nested = f"{MARKER}\n- ```bash\n  # Undo: x\n  kubectl delete pod x\n  ```\n"
    assert fails(tmp_path, nested, "not on the allow-list")
    quoted = f"> {MARKER[2:]}\n> > ```bash\n> > # Undo: x\n> kubectl delete pod x\n> > ```\n"
    assert fails(tmp_path / "b", quoted)


def test_comment_after_pipe_does_not_continue(tmp_path):
    found = run(tmp_path, bash("kubectl get pods |# \\", "kubectl delete pod x"))
    assert any("kubectl delete" in m for m in messages(found))


def test_console_root_prompt_and_comment_continuation(tmp_path):
    assert fails(tmp_path, "```console\n# kubectl delete pod x\n```\n")
    assert fails(tmp_path / "b", "```console\n$ kubectl get pods # \\\nkubectl delete pod x\n```\n")


def test_line_numbers_follow_the_parser(tmp_path):
    found = run(
        tmp_path,
        "text\n\n- item\n\n    ```bash\n    kubectl get pods\n    kubectl delete x\n    ```\n",
    )
    assert [f.line for f in found] == [15]


# Round-4 review: prose that names kubectl without being a command (Ruling R15).
@pytest.mark.parametrize(
    "body",
    [
        "We use the\nkubectl tool to read state.\n",
        "Run `$ kubectl get pods` first.\n",
        "Para:\n$ kubectl get pods\n",
        "The `kubectl` binary.\n",
        "The `kubectl` binary and the kubectl guard.\n\n## kubectl logs\n",
    ],
)
def test_prose_mentions_of_kubectl_are_fine(tmp_path, body):
    assert run(tmp_path, body) == []


def test_prose_command_with_a_kubectl_command_name_is_still_checked(tmp_path):
    assert fails(tmp_path, "Never run `kubectl delete pod x` here.\n", "kubectl delete")
    assert fails(tmp_path / "b", "Never run `$ kubectl delete pod x`.\n", "kubectl delete")
    assert fails(tmp_path / "c", "Or `kubectl -n prod delete pod x`.\n", "kubectl delete")


def test_kubectl_commands_list_names_writes_and_reads():
    names = set(load_allowlist()["kubectl_commands"])
    assert {"get", "describe", "logs", "delete", "apply", "patch", "exec", "drain"} <= names
    assert "tool" not in names and "binary" not in names


def test_inline_code_reports_the_line_it_is_on(tmp_path):
    found = run(tmp_path, "First line.\nSecond `kubectl delete pod x`.\n")
    assert [f.line for f in found] == [10]


@pytest.mark.parametrize("sep", ["\u2028", "\x0c", "\x85"])
def test_unicode_line_separators_do_not_shift_lines(tmp_path, sep):
    fix = f"x{sep}y\n\n{MARKER}\n```bash\n# Undo: z\nkubectl delete pod x\n```\n"
    assert run(tmp_path, refs={"r.md": fix}) == []
    plain = f"x{sep}y\n\n```bash\nkubectl get pods\nkubectl delete x\n```\n"
    found = run(tmp_path / "b", refs={"r.md": plain})
    assert [f.line for f in found] == [5]


@pytest.mark.parametrize(
    ("line", "flag"),
    [
        ("kubectl get pods -w", "-w"),
        ("kubectl get pods -Aw", "-w"),
        ("kubectl get pods --watch", "--watch"),
        ("kubectl get pods --watch-only", "--watch-only"),
        ("kubectl get pods --watch=true", "--watch"),
        ("kubectl logs my-app -f", "-f"),
        ("kubectl logs my-app --follow", "--follow"),
        ("kubectl get -f pod.yaml", "-f"),
        ("kubectl describe --filename=pod.yaml", "--filename"),
        ("kubectl get -k ./overlay", "-k"),
        ("kubectl get --kustomize ./overlay", "--kustomize"),
        ("kubectl get pods -o go-template-file=t.tmpl", "-o go-template-file"),
        ("kubectl get pods -ojsonpath-file=t.txt", "-o jsonpath-file"),
        ("kubectl get pods -o=template-file=t.tmpl", "-o template-file"),
        ("kubectl get pods --output jsonpath-file=t.txt", "-o jsonpath-file"),
        ("kubectl get pods --output=go-template-file=t", "-o go-template-file"),
    ],
)
def test_blocking_and_file_reading_flags_fail(tmp_path, line, flag):
    found = messages(run(tmp_path, bash(line)))
    assert f"flag would block or read local files: {flag}" in found, (line, found)


# Ask-first blocks: commands the agent runs only after the user approves them.


def ask(*lines: str) -> str:
    return f"{ASK_MARKER}\n" + bash(*lines)


@pytest.mark.parametrize(
    "lines",
    [
        ("kubectl exec my-pod -n my-namespace -- nslookup my-app",),
        ("kubectl exec my-pod -n my-namespace -c app -- cat /etc/resolv.conf",),
        ("kubectl exec my-pod -n my-namespace -- wget -qO- http://my-app:8080/",),
        ("kubectl exec my-pod -n my-namespace -- curl -sS -m 5 http://my-app:8080/healthz",),
        ("kubectl exec cilium-abcde -n kube-system -c cilium-agent -- cilium-dbg status",),
        ("kubectl exec cilium-abcde -n kube-system -c cilium-agent -- cilium-dbg endpoint list",),
        ("kubectl exec cilium-abcde -n kube-system -c cilium-agent -- cilium-health status",),
        ("kubectl exec cilium-abcde -n kube-system -c cilium-agent -- hubble observe --last 50",),
        ("kubectl exec my-pod -n my-namespace -c istio-proxy -- pilot-agent request GET clusters",),
        (
            "kubectl rollout undo deployment/my-app -n my-namespace",
            "# Undo: kubectl rollout undo deployment/my-app -n my-namespace",
        ),
        ("kubectl uncordon my-node", "# Undo: kubectl cordon my-node"),
        ("kubectl get pods -n my-namespace",),
    ],
)
def test_ask_first_allows_listed(tmp_path, lines):
    assert run(tmp_path, ask(*lines)) == []


@pytest.mark.parametrize(
    "line",
    [
        "kubectl delete pod my-pod",
        "kubectl drain my-node",
        "kubectl replace --force -f x.yaml",
        "kubectl apply -f x.yaml",
        "kubectl exec my-pod -- rm -rf /data",
    ],
)
def test_ask_first_rejects_destructive(tmp_path, line):
    found = messages(run(tmp_path, ask(line, "# Undo: none")))
    assert any("not on the ask-first allow-list" in m for m in found), (line, found)


def test_ask_first_change_needs_undo(tmp_path):
    found = messages(run(tmp_path, ask("kubectl scale deployment/my-app --replicas=3")))
    assert found == ["ask-first change needs an '# Undo:' line"]
    assert run(tmp_path / "b", ask("kubectl exec my-pod -- nslookup my-app")) == []


@pytest.mark.parametrize(
    ("line", "expect"),
    [
        ("kubectl exec -it my-pod -- sh", "not on the ask-first allow-list"),
        ("kubectl exec my-pod -i -- cat /etc/hosts", "not on the ask-first allow-list"),
        ("kubectl exec my-pod -- bash -c 'cat /etc/hosts'", "not on the ask-first allow-list"),
        ("kubectl exec my-pod -- env", "Secret access is not allowed"),
        ("kubectl exec my-pod -- printenv", "Secret access is not allowed"),
        ("kubectl exec my-pod -- cat /proc/1/environ", "Secret access is not allowed"),
        (
            "kubectl exec my-pod -- cat /var/run/secrets/kubernetes.io/serviceaccount/token",
            "Secret access is not allowed",
        ),
    ],
)
def test_ask_first_rejects_shells_and_secret_dumps(tmp_path, line, expect):
    found = messages(run(tmp_path, ask(line)))
    assert any(expect in m for m in found), (line, found)


def test_ask_marker_matches_constraint():
    assert ASK_MARKER == "> Ask first: the agent runs this only after the user approves it."


def test_ask_marker_must_be_directly_above_the_fence(tmp_path):
    body = f"{ASK_MARKER}\n\nSome words.\n\n" + bash("kubectl uncordon my-node")
    assert any("not on the allow-list" in m for m in messages(run(tmp_path, body)))


def test_extract_blocks_marks_ask():
    block = extract_blocks(f"{ASK_MARKER}\n\n```bash\nx\n```\n")[0]
    assert block.is_ask
    assert not block.is_fix


def test_ask_first_ps_listed_arguments_pass(tmp_path):
    assert run(tmp_path, ask("kubectl exec my-pod -- ps -ef")) == []
    assert run(tmp_path / "b", ask("kubectl exec my-pod -- ps aux")) == []


@pytest.mark.parametrize(
    "line",
    [
        "kubectl exec my-pod -- curl -s http://169.254.169.254/latest/meta-data/",
        "kubectl exec my-pod -- wget -qO- http://metadata.google.internal/computeMetadata/v1/",
        "kubectl exec my-pod -- curl -s http://[fd00:ec2::254]/latest/meta-data/",
        "kubectl exec my-pod -- cat /etc/my-app/password",
        "kubectl exec my-pod -- cat /etc/shadow",
        "kubectl exec my-pod -- ls /etc/my-app/credentials",
        "kubectl exec my-pod -- cat /var/run/my-app/token",
    ],
)
def test_ask_first_rejects_credential_reads(tmp_path, line):
    found = messages(run(tmp_path, ask(line)))
    assert "Secret access is not allowed" in found, (line, found)


@pytest.mark.parametrize(
    "lines",
    [
        (
            "kubectl taint nodes my-node example.com/key=value:NoSchedule",
            "# Undo: kubectl taint nodes my-node example.com/key=value:NoSchedule-",
        ),
        (
            "kubectl taint nodes my-node example.com/key:NoExecute-",
            "# Undo: kubectl taint nodes my-node example.com/key=value:NoExecute",
        ),
        (
            "kubectl patch deployment my-app -n my-namespace --type=merge -p '{}'",
            "# Undo: kubectl rollout undo deployment/my-app -n my-namespace",
        ),
        (
            "kubectl scale statefulset/my-app --replicas=3 -n my-namespace",
            "# Undo: kubectl scale statefulset/my-app --replicas=2 -n my-namespace",
        ),
    ],
)
def test_ask_first_allows_narrow_changes(tmp_path, lines):
    assert run(tmp_path, ask(*lines)) == []


@pytest.mark.parametrize("lang", ["text", "yaml", "json"])
def test_ask_first_needs_a_shell_fence(tmp_path, lang):
    body = f"{ASK_MARKER}\n```{lang}\nkubectl scale deployment/my-app --replicas=0\n```\n"
    assert "ask-first block needs a shell language" in messages(run(tmp_path, body))


@pytest.mark.parametrize(
    "line",
    [
        "kubectl exec my-pod -- cat /mnt/secrets-store/db-password",
        "kubectl exec my-pod -- cat /etc/my-app/api-token",
        "kubectl exec my-pod -- curl -s http://169.254.169.254/latest/meta-data/iam/security-credentials/",
        "kubectl exec my-pod -- curl -s http://100.100.100.200/latest/meta-data/",
    ],
)
def test_ask_first_rejects_secret_substrings(tmp_path, line):
    assert "Secret access is not allowed" in messages(run(tmp_path, ask(line)))


def test_ask_first_undo_line_is_checked_for_secrets(tmp_path):
    body = ask("kubectl uncordon my-node", "# Undo: kubectl get secret my-secret -o yaml")
    assert "Secret access is not allowed" in messages(run(tmp_path, body))


def test_ask_first_allows_ordinary_hosts(tmp_path):
    for i, url in enumerate(
        [
            "http://my-app:8080/healthz",
            "https://my-app.my-namespace.svc.cluster.local/",
            "http://10.96.0.10/",
            "https://example.com/",
        ]
    ):
        assert run(tmp_path / str(i), ask(f"kubectl exec my-pod -- curl -sS {url}")) == [], url


@pytest.mark.parametrize(
    "line",
    [
        "kubectl exec my-pod -- curl -X POST http://my-app/",
        "kubectl exec my-pod -- curl -o /tmp/x http://my-app/",
        "kubectl exec my-pod -- wget http://my-app/",
        "kubectl exec my-pod -- ps eww",
        "kubectl exec my-pod -- hostname my-new-name",
        "kubectl taint nodes my-node example.com/key=value:NoExecute",
        "kubectl patch namespace my-namespace --type=merge -p '{}'",
        "kubectl label pods --all app- -n my-namespace",
    ],
)
def test_ask_first_leaves_arguments_to_the_user_and_reviewers(tmp_path, line):
    # The user sees each ask-first command before it runs, so the checker only checks
    # the verb, the exec program and Secret access.
    assert run(tmp_path, ask(line, "# Undo: none")) == [], line


def test_auth_can_i_may_impersonate(tmp_path):
    """`auth can-i` only asks a question, so --as and --as-group are allowed there."""
    body = bash(
        "kubectl auth can-i list pods -n my-namespace --as=system:serviceaccount:my-namespace:my-app",
        "kubectl auth can-i --list -n my-namespace --as system:serviceaccount:my-namespace:my-app",
        "kubectl auth can-i get nodes --as=jane --as-group=my-group",
    )
    assert run(tmp_path, body) == []


@pytest.mark.parametrize(
    "line",
    [
        "kubectl get pods --as=system:admin",
        "kubectl describe pod my-app --as-group=system:masters",
        "kubectl auth whoami --as=jane",
        "kubectl auth can-i list pods --as-uid=1",
        "kubectl --as=jane auth can-i list pods",
    ],
)
def test_impersonation_elsewhere_is_still_a_finding(tmp_path, line):
    assert "global flag not allowed" in messages(run(tmp_path, bash(line))), line

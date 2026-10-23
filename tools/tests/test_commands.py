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
        if files:
            (skill_dir / sub).mkdir()
        for name, text in files.items():
            (skill_dir / sub / name).write_text(text, encoding="utf-8")
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
    assert messages(found) == ["forbidden flag --as"]
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
    assert run(tmp_path, bash("kubectl get pods | awk '{print $1}'")) == []
    assert run(tmp_path / "b", bash("kubectl get pods | awk '$3 > 5'")) == []


def test_unbalanced_quote_is_a_finding_not_a_crash(tmp_path):
    assert messages(run(tmp_path, bash("kubectl get pods -l 'app=x"))) == ["cannot parse command"]


def test_pipe_to_filter_passes(tmp_path):
    assert run(tmp_path, bash("kubectl get pods -A | grep -v Running")) == []
    assert run(tmp_path / "b", bash("kubectl get pods -A|grep -v Running|wc -l")) == []


def test_pipe_to_other_command_fails(tmp_path):
    found = run(tmp_path, bash("kubectl get pods -o name | xargs kubectl delete"))
    assert any("filter" in m for m in messages(found))


def test_sed_in_place_fails(tmp_path):
    for line in (
        "kubectl get pods | sed -i s/a/b/ f",
        "kubectl get pods | sed -i.bak s/a/b/ f",
        "kubectl get pods | sed --in-place s/a/b/ f",
        "kubectl get pods | sed -ni p f",
    ):
        found = run(tmp_path / str(abs(hash(line))), bash(line))
        assert any("in-place" in m for m in messages(found)), line


def test_sed_plain_passes(tmp_path):
    assert run(tmp_path, bash("kubectl get pods | sed -n '1,3p'")) == []
    assert run(tmp_path / "b", bash("kubectl get pods | sed 's/a/b/g'")) == []


@pytest.mark.parametrize(
    "filt",
    [
        "sed 's/a/b/w out.txt'",
        "sed 's/a/b/e'",
        "sed -n 'w out.txt'",
        "sed e",
        "awk '{system(\"rm x\")}'",
        "awk '{print $1 > \"out.txt\"}'",
        "awk '{print $1 | \"sh\"}'",
        "awk 'BEGIN{\"date\" | getline d}'",
        "sort -o out.txt",
        "sort --output=out.txt",
        "sort -ro out.txt",
        "sort -uo out.txt",
        "yq -i .a=1 f.yaml",
        "yq --inplace .a=1 f.yaml",
        "tail -f out",
        "tail -F out",
        "tail --follow out",
        "tail -nf out",
        "head -qF out",
        "uniq in.txt out.txt",
    ],
)
def test_filters_that_write_or_block_fail(tmp_path, filt):
    found = run(tmp_path, bash(f"kubectl get pods | {filt}"))
    assert found, filt


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
        assert any(m.startswith("forbidden flag") for m in messages(found)), line


def test_forbidden_flag_in_filter_segment_is_not_checked(tmp_path):
    assert run(tmp_path, bash("kubectl get pods | grep -s foo")) == []


def test_yaml_block_is_ignored(tmp_path):
    assert run(tmp_path, "```yaml\nkubectl delete pod x\nkind: Pod\n```\n") == []


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

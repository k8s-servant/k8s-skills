# Contributing

Thank you for helping. This repository holds read-only Kubernetes skills for AI agents.
Every skill must be correct, safe to follow, and tested against a real cluster.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
source .venv/bin/activate
```

Before every commit:

```bash
ruff check . && ruff format --check . && pytest && python -m tools.skillcheck check
python -m tools.skillcheck manifests --check
```

## Skill conventions

- A skill is `skills/<name>/SKILL.md`, with optional `references/*.md` and optional
  `scripts/` (read-only scripts only).
- `name`: lowercase letters, digits and hyphens, at most 64 characters, equal to the
  folder name, starting with `k8s-`, never containing `claude` or `anthropic`. The pattern
  is `k8s-<subject>-<job>` (for example `k8s-network-troubleshooting`). `k8s-triage` is the
  only name without a subject.
- Frontmatter has only `name`, `description`, `license` (`Apache-2.0`), `compatibility`,
  `metadata` and `allowed-tools`. `description` is 1 to 1024 characters and starts with
  `Use when`, naming the symptoms that should trigger the skill. `metadata` includes
  `verified-with` (for example `kubernetes 1.37`) and `verified-on` (`YYYY-MM-DD`).
- `SKILL.md` is at most 500 lines. Its H2 sections, in order: `When to use`,
  `Investigate`, `Read the results`, `Proposed fix`, `Sources`.
- Hand-offs between skills are by skill name in the body. No agent-specific tool names.
- Use placeholders only: `my-namespace`, `my-app`, `example.com`. No real cluster names,
  hostnames, registries, company names or personal data.
- Start from the templates: [templates/SKILL.template.md](templates/SKILL.template.md)
  (copy it to `skills/<name>/SKILL.md`) and
  [templates/expected.template.md](templates/expected.template.md) (copy it to
  `tests/<skill>/<case>/expected.md`). They are not named `SKILL.md`, so tools that search
  for skills recursively never list a template as a skill.

### Commands in a skill

Investigation commands may use only what is on the allow-list in
`tools/skillcheck/allowlist.yaml`:

- Allow-listed commands and flags only, with literal placeholders such as `my-namespace`.
  No `$VAR` and no `<placeholder>`.
- No `;`, `&&` or redirects. Pipes only to the listed filters, with the listed flags.
- No flags that block or read local files: `-w`/`--watch`, `-f`/`--follow`,
  `-f`/`--filename`, `-k`/`--kustomize`, or `-o` formats ending in `-file`.
- Scripts in `scripts/` may contain only a shebang line, comments and allow-listed
  commands, one per line. No variables, no `set`, no functions or other shell syntax.
- Never read Secrets: no `get`, `describe` or listing of `secret` or `secrets` in any form.
- Fenced blocks need a language (` ```bash `). Indented (4-space) code blocks are rejected.
- In prose, inline code that reads as a kubectl command is checked. Plain mentions of
  kubectl ("the `kubectl` binary") are fine.
- To allow a new command or flag, open a PR that changes `allowlist.yaml`. The allow-list
  only grows by review, and never turns into a deny-list.

### Proposed fixes

A fix is the only place a command that changes the cluster may appear. Put it in a
top-level fenced block directly under this exact line:

```markdown
> Proposed fix: review before running. The agent does not run this.
```

The block must contain an `# Undo:` line that restores the state you found. A fix block
may use any shell, except access to Secrets.

### What the checker enforces, and its limits

`python -m tools.skillcheck check` checks frontmatter, section order, size, names,
the commands and fix blocks above, and that scenarios exist. It fails closed: whatever it
cannot recognise as safe is a finding.

It is a guardrail against honest authoring mistakes, not a sandbox. Known limits:

- A fix block may use any shell, so `sh -c`, `eval` or nested quoting can hide a Secret name.
- `$[` arithmetic and backslash tricks in prose.
- Glob patterns such as `secre[t]s`.
- yq `load()`.
- `-v=9` logging.
- A prose command whose second word is not a kubectl command name (fenced blocks are
  still checked in full).

Deliberate obfuscation is caught by human review, so reviewers read every command.

## Scenarios and the test kit

Every skill needs at least two scenarios in `tests/<skill>/<case>/`: `setup.sh`,
`break.sh`, `cleanup.sh` and `expected.md` (Prompt, Cause, Evidence, Acceptable fixes,
Wrong answers). Cloud-only behaviour that kind cannot reproduce is checked against the
docs, and the PR says so.

The kit creates a throwaway [kind](https://kind.sigs.k8s.io) cluster named
`k8s-skills-test`, with its own kubeconfig in `.kube/`. It never touches your other
clusters or your current context. The agent under test gets a view-only kubeconfig, so it
cannot change the cluster even by mistake.

```bash
tests/cluster.sh up                       # create the cluster (add --cni calico for NetworkPolicy cases)
tests/run.sh <skill> <case>               # set up and break the scenario, print the prompt and KUBECONFIG
# Give the agent the prompt and the printed KUBECONFIG, then compare its answer with expected.md.
tests/run.sh --cleanup <skill> <case>     # undo the scenario
tests/cluster.sh down                     # delete the cluster
```

Judging is manual against `expected.md`: did the agent name the Cause, point at the
Evidence and propose an Acceptable fix, and did it run no write command?

## Review checklist

A skill is merged only when:

- The upstream documentation was checked, and every page used is listed under `Sources`.
- At least two scenarios exist and were run with at least one agent, and the runs are
  recorded in the PR (case, agent, model, kind and Kubernetes version, cause named, fix
  acceptable).
- `skillcheck` passes, and the reviewer read the commands (the checker is not a sandbox).
- The skill uses placeholders only and contains no site-specific facts.

## Commits, versions and releases

- Use Conventional Commits and PR titles: `feat(skills): ...`, `fix: ...`, `docs: ...`.
  release-please builds the changelog and versions from them.
- Never create or edit `CHANGELOG.md`, and never bump a version by hand.
- The install manifests (`.claude-plugin/marketplace.json`, `gemini-extension.json`,
  `plugin.json`) are generated. After adding or renaming a skill run
  `python -m tools.skillcheck manifests --write` and commit the result.
- To try the release zips: `python -m tools.skillcheck package --out dist`.

# AGENTS.md

Guidance for AI coding assistants working in this repository. Humans: see
[CONTRIBUTING.md](CONTRIBUTING.md). `CLAUDE.md` only imports this file.

## Project

k8s-skills is a set of Kubernetes troubleshooting skills (`skills/<name>/SKILL.md`) for
any AI agent, which read first and ask before changing anything, plus the tooling that
checks them (`tools/skillcheck`) and a kind-based test kit (`tests/`).

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # setup
.venv/bin/pytest                                         # tests
.venv/bin/ruff check . && .venv/bin/ruff format --check .   # lint
.venv/bin/python -m tools.skillcheck check               # check every skill
.venv/bin/python -m tools.skillcheck manifests --write   # regenerate install manifests
.venv/bin/python -m tools.skillcheck manifests --check   # fail if manifests are stale
.venv/bin/python -m tools.skillcheck package --out dist  # release zips
tests/cluster.sh up [--cni calico|cilium] | down          # throwaway kind cluster
tests/addon.sh <name>                                    # install a pinned add-on (names: see the script)
tests/run.sh <skill> <case>                              # run a scenario
tests/run.sh --cleanup <skill> <case>                    # undo a scenario
npx --yes markdownlint-cli2@0.24.0 "**/*.md" "#.venv" "#node_modules"   # markdown lint
```

The test kit only creates and deletes the cluster `k8s-skills-test` (context
`kind-k8s-skills-test`, kubeconfig in `.kube/`). It never touches other clusters or the
current context.

## Rules (must follow)

- **Read first, ask before changing.** Every command is in one of three tiers, each checked
  against `tools/skillcheck/allowlist.yaml`. The allow-lists only grow by review (a PR that
  changes them), and are never turned into deny-lists.
  - **Run freely:** investigation commands from `commands`, anywhere in a skill.
  - **Ask first:** commands from `ask_first` (reversible changes, and `exec` of one
    read-only program), in a fenced block directly under
    `> Ask first: the agent runs this only after the user approves it.`. A change needs an
    `# Undo:` line. The skill tells the agent to run it only after the user approves it.
  - **Never run:** anything destructive or hard to undo, only as a proposed fix in a fenced
    block directly under
    `> Proposed fix: review before running. The agent does not run this.`, with an
    `# Undo:` line, for a human to run.
- **Never read Secrets**, in any command, script or example, in any tier.
- **Placeholders only** (`my-namespace`, `my-app`, `example.com`). This is a public
  repository: no real cluster names, registries, hostnames, tenant IDs, company names or
  personal data.
- **Never create or edit `CHANGELOG.md`** and never bump versions by hand: release-please
  does both.
- **Manifests are generated** (`.claude-plugin/marketplace.json` and `plugin.json`,
  `skills/*/.claude-plugin/plugin.json`, `gemini-extension.json`, `plugin.json`, and the
  `extra-files` in `release-please-config.json`). Run `manifests --write`, do not edit them
  by hand.
- **One copy of each skill**, in `skills/`. No duplicated skill files.
- **Skill shape:** name `k8s-<subject>-<job>` equal to the folder, frontmatter limited to
  the portable fields, `SKILL.md` at most 500 lines, H2 sections in order: When to use,
  Investigate, Read the results, Proposed fix, Sources.
- **Every skill needs at least two kind scenarios** and its upstream docs listed in Sources.
- **TDD for tooling:** write a failing test first. Tests for `tools/` live in `tools/tests/`.
- **Conventional Commits** for commits and PR titles. No attribution lines in commits.
- Before every commit: `ruff check . && ruff format --check . && pytest && python -m tools.skillcheck check`.

## Review feedback

Treat a review (human or bot) as input to verify, not a list of orders. Check each point
against the code or the upstream docs, fix what is right, and reply with evidence when it
is wrong. Read PR conversation comments, review summaries and inline comments.

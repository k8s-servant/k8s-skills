# Contributing

Thank you for helping. This repository holds Kubernetes troubleshooting skills for AI
agents that read first and ask before changing anything. Every skill must be correct,
safe to follow, and tested against a real cluster.

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

Every command is in one of three tiers:

| Tier | Where it goes | Allow-list |
|---|---|---|
| Run freely | Anywhere: investigation steps, prose | `commands` |
| Ask first | A block directly under the ask-first marker (below) | `commands` plus `ask_first` |
| Never run | A block directly under the proposed-fix marker (below) | Anything except Secrets |

Investigation commands may use only what is on the `commands` allow-list in
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
- To allow a new command or flag, open a PR that changes `allowlist.yaml`. The allow-lists
  only grow by review, and never turn into deny-lists.

### Ask first: changes the agent runs after approval

A reversible change, or a read-only check inside a container, goes in a top-level fenced
block directly under this exact line:

```markdown
> Ask first: the agent runs this only after the user approves it.
```

The skill tells the agent to show the command, say what it changes and how to undo it,
and run it only after the user says yes. If the agent's RBAC refuses it, the agent gives
the command to the user to run. Each command must be on `commands` or `ask_first`:

- The block must use a shell language (` ```bash `).
- Changes: `set image`, `set resources`, `rollout undo`, `rollout restart`,
  `rollout pause`, `rollout resume`, `scale`, `patch`, `cordon`, `uncordon`, `label`,
  `annotate`, `taint`. A block with a change needs an `# Undo:` line that restores the
  state you found.
- `kubectl exec POD [-n ns] [-c container] -- PROGRAM [args]`, with one program from
  `ask_first.in_pod` (`nslookup`, `dig`, `getent`, `curl`, `wget`, `cat`, `ls`, `ps`,
  `df`, `id`, `hostname`). No shell, and no `-i`/`-t`/`--stdin`/`--tty`.
- These count as Secret access, anywhere in the command or its `# Undo:` line: `env`,
  `printenv`, and anything with `environ`, `serviceaccount`, `token`, `password`,
  `credential`, `shadow`, `secrets-store` or a usual cloud metadata address
  (`169.254.169.254`, `metadata.google.internal`) in it.

The checker does not check arguments, because the user sees each command before it runs.
Reviewers and the user check them instead:

- A change should name one object: no `--all`, `-A` or `-l` on a change, and no
  `--patch-file` the user cannot see. `taint` should not add `NoExecute`, which evicts
  every pod on the node.
- An exec program should only read: no `curl` that sends or saves data, no `wget`
  without `-O-` (it would write a file), no `ps e` (it prints every process's
  environment), and no `hostname` argument (it renames the host).

`port-forward` and `debug` are not on the list: `port-forward` never returns, and `debug`
adds a container that cannot be removed.

### Proposed fixes: changes the agent never runs

Anything destructive or hard to undo (`delete`, `drain`, `replace`, `apply`, ...) is
never run by the agent. Put it in a top-level fenced block directly under this exact
line, and say in the text why the agent must not run it:

```markdown
> Proposed fix: review before running. The agent does not run this.
```

The block must contain an `# Undo:` line that restores the state you found. A fix block
may use any shell, except access to Secrets.

### What the checker enforces, and its limits

`python -m tools.skillcheck check` checks frontmatter, section order, size, names,
the commands, ask-first blocks and fix blocks above, and that scenarios exist. It fails
closed: whatever it cannot recognise as safe is a finding.

It is a guardrail against honest authoring mistakes, not a sandbox. Known limits:

- A fix block may use any shell, so `sh -c`, `eval` or nested quoting can hide a Secret name.
- Ask-first arguments are not checked beyond the Secret words above, so an ask-first
  `cat`, `ls`, `curl` or `wget` can reach a mounted Secret file or a metadata endpoint
  whose path or address gives no sign of it. Reviewers read each path and URL, and the
  user sees each command before approving it.
- `$[` arithmetic and backslash tricks in prose.
- Glob patterns such as `secre[t]s`.
- yq `load()`.
- `-v=9` logging.
- Long kubectl flags after the subcommand pass unless they are a disallowed global flag
  or one that blocks or reads local files; there is no per-subcommand list.
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
clusters or your current context. It needs `kind`, `kubectl` and Docker: kind's
Podman provider is not supported, because some scenarios use `docker exec` on a node.
The `k8s-helm-troubleshooting` scenarios also need Helm 4.
The agent under test gets a view-only kubeconfig, so it
cannot change the cluster even by mistake: the built-in `view` role in every namespace,
plus read access to the cluster-scoped objects `view` leaves out (nodes, PersistentVolumes,
StorageClasses, the CSI objects, admission webhook configurations and cert-manager
ClusterIssuers), to Argo CD's and Gatekeeper's objects, which no aggregated role covers, and to
ValidatingAdmissionPolicies. To test what an agent with access to
one namespace sees, put an `agent-scope` file in the case folder with the namespace name
on its first line. The agent then gets `view` in that namespace only, and no node access,
and its kubeconfig context points at that namespace, as a developer's usually does.

```bash
tests/cluster.sh up                       # create the cluster (--cni calico for NetworkPolicy cases, --workers N for node cases)
tests/addon.sh cert-manager               # install a pinned add-on (setup.sh scripts call this)
tests/run.sh <skill> <case>               # set up and break the scenario, print the prompt and KUBECONFIG
# Give the agent the prompt and the printed KUBECONFIG, then compare its answer with expected.md.
tests/run.sh --cleanup <skill> <case>     # undo the scenario
tests/cluster.sh down                     # delete the cluster
```

Judging is manual against `expected.md`: did the agent name the Cause, point at the
Evidence and propose an Acceptable fix, and did it run no change without the user's
approval and no "never run" command?

An ecosystem skill's scenarios install the tool with `tests/addon.sh <name>` from their
`setup.sh`. To add a tool, pin its version and the sha256 of its install manifest in
`tests/versions.env` (download the file and run `shasum -a 256` on it), and add a case
to `tests/addon.sh` with the manifest URL and the namespace to wait for. The script
refuses a manifest whose checksum does not match.

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
- To release, merge the release PR that release-please keeps open. It is opened with a
  GitHub App token so the required checks run on it. If the Release run fails at the
  token step, check the `RELEASE_APP_CLIENT_ID` variable and the
  `RELEASE_APP_PRIVATE_KEY` secret, and that the App is still installed on the
  repository.

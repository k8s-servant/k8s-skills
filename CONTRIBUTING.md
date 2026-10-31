# Contributing

Thank you for helping. This repository holds Kubernetes troubleshooting skills for AI
agents that read first and ask before changing anything. Every skill must be correct,
safe to follow, and tested against a real cluster.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.txt
source .venv/bin/activate
```

The dev dependencies are pinned by version in `requirements-dev.in` and by hash, with
everything they pull in, in `requirements-dev.txt`, which CI installs with
`--require-hashes`. To change one, edit `requirements-dev.in` and regenerate the lock
file with the command at the top of `requirements-dev.txt` (it needs
[uv](https://docs.astral.sh/uv/)). If a dependency update leaves a hash out of date,
the install in CI fails, so a stale lock file cannot slip through. On such a PR (a
Dependabot one too), bump the pin in `requirements-dev.in` and regenerate the lock file
with the header command.

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
- Global flags that change the identity, server or local files (`--as`, `--server`,
  `--kubeconfig`, ...) are not allowed, except where `subcommand_flags_allowed` lists
  them for one subcommand: `kubectl auth can-i` may use `--as` and `--as-group`, as it
  only asks the API server a question.
- No flags that block or read local files: `-w`/`--watch`, `-f`/`--follow`,
  `-f`/`--filename`, `-k`/`--kustomize`, or `-o` formats ending in `-file`.
- Cloud skills may also run the Azure CLI's read-only `show`, `list` and `get`
  subcommands listed under `az`, with the flags in `az_flags`. The subcommand comes
  first, and no argument may start with `@` (az would read it from a local file).
  `get-credentials`, `command invoke`, `check-acr` and `kollect` are not on the list,
  because they write credentials or run something in the cluster. Every `az` change is a
  proposed fix, never ask-first.
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
  `df`, `id`, `hostname`, in the Cilium agent `cilium-dbg`, `cilium-health`, `hubble`,
  and in Istio's proxy `pilot-agent`). No shell, and no `-i`/`-t`/`--stdin`/`--tty`. The Cilium tools and
  `pilot-agent` can also change state; a skill uses only their reading subcommands (for
  `pilot-agent`, `request GET` on a reading admin path), and
  reviewers check that.
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
clusters or your current context. It needs `kind`, `kubectl` and Docker: kind's Podman
provider is not supported, because some scenarios use `docker exec` on a node. The
`k8s-helm-troubleshooting` scenarios also need Helm 4. The agent under test gets a
view-only kubeconfig, so it cannot change the cluster even by mistake: the built-in `view`
role in every namespace, plus read access to the cluster-scoped objects `view` leaves out
(nodes, PersistentVolumes, StorageClasses, the CSI objects, admission webhook
configurations and cert-manager ClusterIssuers), to Argo CD's and Gatekeeper's objects,
which no aggregated role covers, and to ClusterExternalSecrets,
ValidatingAdmissionPolicies, the RBAC objects (Roles, ClusterRoles and their bindings),
APIServices, CRDs and the API Priority and Fairness objects (FlowSchemas and
PriorityLevelConfigurations).
To test what an agent with access to one namespace sees, put an `agent-scope` file in the
case folder with the namespace name on its first line. The agent then gets `view` in that
namespace only, and no node access, and its kubeconfig context points at that namespace,
as a developer's usually does.

```bash
tests/cluster.sh up                       # create the cluster (--cni calico for NetworkPolicy cases, --cni cilium for Cilium cases, --workers N for node cases)
tests/addon.sh cert-manager               # install a pinned add-on (setup.sh scripts call this)
tests/run.sh <skill> <case>               # set up and break the scenario, print the prompt and KUBECONFIG
# Give the agent the prompt and the printed KUBECONFIG, then compare its answer with expected.md.
tests/run.sh --cleanup <skill> <case>     # undo the scenario
tests/try.sh [<skill> <case>]             # for users: cluster if needed, break, print how to point an agent at it
tests/cluster.sh down                     # delete the cluster
```

### From a report to a scenario

A report from the "The agent got it wrong" issue form is turned into a scenario before
the skill is fixed, so the fix is tested against the miss:

1. Reproduce the cause on kind (or in one namespace of a cloud test cluster) as a new
   case: `setup.sh` builds what the reporter had, `break.sh` adds the cause.
2. Write `expected.md` from the report: the reporter's question as the Prompt (with
   placeholders), the real cause and its evidence, and the agent's wrong conclusion
   under Wrong answers.
3. Run an agent with the current skill and confirm it misses, then fix the skill and
   run it again until it passes. Record both runs in the PR, and link the issue.

A report that the agent changed something without asking, or read a Secret, is fixed
first; such a report may also show a gap in the checker or the allow-list.

### Cloud scenarios

A cloud skill (`k8s-aks-*`, `k8s-eks-*`, `k8s-gke-*`) can have scenarios that run on a
real managed cluster you own. Such a case has a `platform` file (`aks`, `eks` or `gke`)
and an `agent-scope` file. It runs only in that one namespace and creates nothing outside
it: the agent's ServiceAccount and its `view` RoleBinding live in the namespace too, and
`cleanup.sh` deletes the namespace. Name the cluster's kubeconfig context explicitly:

```bash
K8S_SKILLS_CLOUD_CONTEXT=my-aks-context tests/run.sh k8s-aks-troubleshooting my-case
K8S_SKILLS_CLOUD_CONTEXT=my-aks-context tests/run.sh --cleanup k8s-aks-troubleshooting my-case
```

Scenarios that run a pod use `curlimages/curl:8.10.1`. If the cluster only admits images
from its own registry (or only signed ones), set `K8S_SKILLS_TEST_IMAGE` to an allowed
image with `sh` and `curl`, for example a mirror of that one. Its pods run as a non-root
user.

The kit copies only that context into the git-ignored `.kube/cloud` and refuses to run
when its current context is anything else. It refuses a cloud case without the variable,
and a kind case or `tests/addon.sh` with it. Use a test cluster: a scenario breaks things
on purpose. Nothing that names the cluster (its name, resource group, subscription, node
names) goes into the repository.

Judging is manual against `expected.md`: did the agent name the Cause, point at the
Evidence and propose an Acceptable fix, and did it run no change without the user's
approval and no "never run" command?

An ecosystem skill's scenarios install the tool with `tests/addon.sh <name>` from their
`setup.sh`. To add a tool, pin its version and the sha256 of its install manifest in
`tests/versions.env` (download the file and run `shasum -a 256` on it), and add a case
to `tests/addon.sh` with the manifest URL and the namespace to wait for. The script
refuses a manifest whose checksum does not match.

## CI

Every pull request runs the checks described in [docs/ci.md](docs/ci.md): lint,
tests, `skillcheck`, shellcheck, markdownlint, link and plugin checks, gitleaks, zizmor,
actionlint, the PR title check and a Claude review. The kind scenarios do not run in CI;
run them yourself as described above.

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
- The install manifests (`.claude-plugin/marketplace.json` and `plugin.json`, one
  `skills/<name>/.claude-plugin/plugin.json` per skill, the `plugin.json` of the hook
  plugins in `plugins/` (listed in `HOOK_PLUGINS` in `tools/skillcheck/manifests.py`),
  `gemini-extension.json`, `plugin.json`) and the `extra-files` list in `release-please-config.json` are generated.
  After adding or renaming a skill run `python -m tools.skillcheck manifests --write` and
  commit the result. Each skill folder is its own Claude Code plugin, so
  `/plugin install <skill>@k8s-skills` installs only that skill.
- To try the release zips: `python -m tools.skillcheck package --out dist`.
- To release, merge the release PR that release-please keeps open. It is opened with a
  GitHub App token so the required checks run on it. If the Release run fails at the
  token step, check the `RELEASE_APP_CLIENT_ID` variable and the
  `RELEASE_APP_PRIVATE_KEY` secret, and that the App is still installed on the
  repository.

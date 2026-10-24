# k8s-skills: design

Status: approved 2026-10-23. See [Changed during implementation](#changed-during-implementation)
for where the build differs from the first draft.

## Intent

A public repository of ready-to-use agent skills for Kubernetes and the tools around it,
for **anyone who runs an AI agent against a cluster**: Claude Code, Codex, GitHub Copilot,
Cursor, Gemini CLI or any other agent that reads the open Agent Skills format
(https://agentskills.io).

The skills live in the repo as real files, not links. A skill teaches an agent how to
investigate a problem: where to look, in what order, how to read what it finds, and
which fix to propose. The skills **read first and ask before changing anything**: the agent
diagnoses freely, runs a reversible change only after the user approves it, and only
proposes anything destructive for a human to run (see "Changed after release").

Why: existing Kubernetes skill collections mostly mix diagnosis with changes the agent
makes itself. A set that reads first, never changes anything without the user's approval,
never runs anything destructive, and is checked against upstream docs and tested on a real
cluster is a gap, and safe to give to any agent.

## Goals

- Skills that work in as many agents as possible, installable in as many ways as possible.
- Every skill checked against the component's official docs and tested on a kind cluster.
- Read-only investigation, with clearly marked changes: ask first for reversible ones, a
  proposed fix for a human to run for destructive ones.
- Generic content that works on any conformant cluster. Cloud-specific knowledge lives in
  its own per-cloud skills.

## Non-goals

- Not a curated link list (despite the "awesome" idea, the content lives here).
- No agent, MCP server or CLI of our own.
- No docs site in the first release; the README is enough.
- k8s-servant stays as it is. Switching its built-in skills to this repo is a later
  decision, made once skills here are ready.

## Anti-goals (a failure even if it works)

- A skill that tells the agent to change the cluster without the user's approval, or to
  run anything destructive itself (delete, drain, replace, apply).
- A skill that reads Secret values.
- Commands, flags or field names written from memory and not checked against upstream docs.
- Site names, company data or a single vendor's tooling in a generic skill.
- A skill merged without a kind test (cloud skills excepted, see Testing).

## Decisions made

| Topic | Decision | Whose |
|---|---|---|
| Name and home | `k8s-servant/k8s-skills` (the existing k8s-servant GitHub org; a separate org is too much) | maintainer |
| Format | One folder per skill with `SKILL.md`, Agent Skills standard | maintainer |
| Behaviour | Read first, ask before changing; destructive fixes only proposed for a human (was: read-only by default, see "Changed after release") | maintainer |
| Install paths | As many as possible (see Distribution) | maintainer |
| Cloud skills | AKS, EKS and GKE each get their own skill | maintainer |
| Granularity | One skill per area, detail in `references/`; one entry triage skill | maintainer |
| Quality | Follow skill-writing practice, check against upstream docs, test on kind | maintainer |
| k8s-servant | Unchanged for now | maintainer |
| License | Apache-2.0, same as k8s-servant | my call |
| First batch | The five skills below | my call, agreed in chat |
| Repo hygiene | Same as k8s-servant: actions pinned to SHAs, `permissions: {}`, Conventional Commits, release-please, gitleaks, review bot | my call |
| Test judging | Manual against a structured `expected.md`; no scoring harness in the first release | my call |
| Command rules | Allow-list for Investigate commands and scripts; Secrets excluded entirely | my call |
| Install paths vs single copy | Single copy wins; a path that needs duplication is left out for now | my call |
| Install one or all | Every install path offers both: one skill, or the whole set | maintainer |
| Naming | `k8s-<subject>-<job>` for every skill | maintainer |
| Plugins | Claude Code marketplace lists a `k8s-skills` bundle plus one entry per skill, all pointing at the same `skills/` folders | my call |

## Skills

### First batch: core Kubernetes

| Skill | Covers |
|---|---|
| `k8s-triage` | Entry point. From a symptom to the right area; reading events, `describe` output and conditions; when to hand over to which skill. |
| `k8s-workload-troubleshooting` | Pods Pending, CrashLoopBackOff, ImagePullBackOff, failing probes, OOMKilled and limits, rollouts that do not progress, Jobs and CronJobs that fail. One reference file per topic. |
| `k8s-node-troubleshooting` | NotReady, memory, disk and PID pressure, allocatable capacity, taints, cluster autoscaler not scaling. |
| `k8s-network-troubleshooting` | Services without endpoints, wrong selectors or ports, DNS resolution, NetworkPolicy blocking traffic, Ingress or Gateway not routing. |
| `k8s-storage-troubleshooting` | PVCs stuck in Pending, StorageClass and provisioner problems, attach and mount errors, volumes filling up. |

### Ecosystem skills

One skill per tool, so each description names its tool and the agent picks the right one.
Order: the most used tools first, and those easy to run on kind before the heavy ones.

| Batch | Skills |
|---|---|
| 1. Delivery | `k8s-cert-manager-troubleshooting`, `k8s-flux-troubleshooting`, `k8s-argocd-troubleshooting`, `k8s-helm-troubleshooting` |
| 2. Policy and secrets | `k8s-kyverno-troubleshooting`, `k8s-gatekeeper-troubleshooting`, `k8s-external-secrets-troubleshooting` |
| 3. Observability | `k8s-prometheus-troubleshooting` (Operator, Alertmanager, rules), `k8s-grafana-troubleshooting` |
| 4. Networking | `k8s-cilium-troubleshooting`, `k8s-istio-troubleshooting`, `k8s-envoy-gateway-troubleshooting` |
| Later candidates | KEDA, Velero, Crossplane, Linkerd, Traefik, CloudNativePG |

Rules for every ecosystem skill (decided with the maintainer, after #42):

- **kubectl first, the tool's CLI optional.** Every investigation works with kubectl
  alone: the tool's custom resources, their status conditions, events and controller
  logs. Read-only commands of the tool's own CLI (`flux get`, `cmctl status`,
  `cilium status`, `istioctl analyze`) are an extra "if installed" step, added to
  `allowlist.yaml` in the skill's PR. Argo CD's CLI needs its own login, so it stays
  optional there.
- **Helm reads Secrets.** Helm keeps each release, values included, in a Secret, so
  `helm status`, `helm history` and `helm get` read Secrets. The Helm skill investigates
  with kubectl (the `meta.helm.sh/*` annotations, the rendered objects, events) and gives
  `helm` commands to the user to run, as proposed fixes with "nothing to undo".
- **Secrets stay unread** in External Secrets too: the skill reads `ExternalSecret`,
  `SecretStore` and `ClusterSecretStore` status, never the target Secret.
- **No separate Envoy skill.** Envoy is the proxy inside Istio and Envoy Gateway; reading
  its config belongs to those two skills. The Gateway API itself stays in
  `k8s-network-troubleshooting`.
- **Scenarios** install the tool on kind from a pinned version in `tests/versions.env`,
  with the manifest checked against a pinned checksum, as for Calico.

### Clouds

`k8s-aks-troubleshooting`, `k8s-eks-troubleshooting`, `k8s-gke-troubleshooting` (node
pools, cloud load balancers, identity, managed add-ons), checked against provider docs,
and on a real cluster when someone has an account.

### Skill conventions

- `skills/<name>/SKILL.md`, optional `references/*.md`, optional `scripts/` (read-only
  scripts only).
- Frontmatter uses **only the portable fields**: `name`, `description`, `license`,
  `compatibility`, `metadata`, `allowed-tools`. No agent-specific extras, so the claude.ai
  zip upload keeps working.
- **Naming pattern `k8s-<subject>-<job>`** for every skill (`k8s-network-troubleshooting`,
  `k8s-flux-troubleshooting`, later e.g. `k8s-upgrade-readiness`). The prefix avoids clashes
  in the shared skill folders most agents use and marks the skill's domain; the job says
  what kind of skill it is. `k8s-triage` is the one name without a subject.
- `name`: lowercase letters, digits and hyphens, at most 64 characters, equal to the folder
  name, never containing "claude" or "anthropic". `description`: at most 1024 characters,
  starting with "Use when ..." and naming the symptoms that should trigger it. For
  `k8s-triage`: "Use when something is wrong in a cluster and it is not yet clear where".
  Hand-offs between skills are by skill name in the body ("continue with
  `k8s-node-troubleshooting`"), no agent-specific mechanism.
- `metadata` carries `verified-with` (the component versions the skill was checked against,
  e.g. `kubernetes 1.34`) and `verified-on` (date).
- The body follows one shape: **When to use** → **Investigate** (ordered steps with the
  read-only commands) → **Read the results** (what each finding means) → **Proposed fix**
  → **Sources** (links to the upstream docs used).
- Commands are plain `kubectl` (and the tool's own read-only CLI where one exists, e.g.
  `flux get`, `argocd app get`). kubectl is the common language; an agent with MCP tools
  can use the equivalent call. No agent-specific tool names.
- Investigate commands come from an **allow-list** (never a deny-list, same principle as
  k8s-servant's kubectl guard): `get`, `describe`, `logs`, `events`, `top`, `explain`,
  `auth can-i`, `api-resources`, `api-versions`, `version`, `cluster-info`, plus listed
  read-only subcommands of tool CLIs (`flux get`, `argocd app get`, ...), which a skill adds
  to the allow-list in the same PR. Anything not listed fails CI. Secrets are excluded
  entirely: no `get`, `describe` or listing of `secret`/`secrets` in any form. `logs` is
  allowed; skills tell the agent not to repeat credentials it sees in output.
- Scripts in `scripts/` are checked against the same allow-list.
- **Proposed fix** blocks are the only place a write command may appear. Each one is
  introduced by the line `> Proposed fix: review before running. The agent does not run this.`
  and states what it changes and how to undo it. CI checks that every fenced block with a
  command outside the allow-list sits directly under that marker line.
- Placeholders only: `my-namespace`, `my-app`, `example.com`.

## Distribution

One canonical copy of each skill in `skills/`. No duplicated skill files anywhere in the
repo; manifests only point at it. **The single copy wins**: an install path that needs
duplicated files, or that cannot be checked by its own validator or a real install, is left
out of the first release and listed in the README as not yet supported.

| Path | What the repo provides |
|---|---|
| `npx skills add k8s-servant/k8s-skills` (Vercel `skills` CLI, many agents) | the `skills/` layout |
| `gh skill install k8s-servant/k8s-skills [skill]` (Copilot, preview) | the `skills/` layout |
| Claude Code plugin: `/plugin marketplace add k8s-servant/k8s-skills`, then `/plugin install k8s-skills@k8s-skills` (all) or `/plugin install k8s-network-troubleshooting@k8s-skills` (one) | `.claude-plugin/marketplace.json`: a bundle entry plus one entry per skill, each with `source: "./"` and `skills: ["./skills/<name>"]` (a root-source entry that lists skills loads only those, per the plugin reference) |
| Codex: `npx skills add k8s-servant/k8s-skills -a codex` | the `skills/` layout; no Codex marketplace file yet (root `plugin.json`, portable agent-plugins schema, is kept for one) |
| Gemini CLI: `gemini skills install <git-url>` or `gemini extensions install <github-url>` | `gemini-extension.json`; extensions load the root `skills/` folder |
| Manual copy into `.agents/skills`, `.claude/skills`, `.github/skills`, `.cursor/skills` | documented in the README |
| claude.ai / Claude API | a zip per skill attached to each GitHub release |

Releases: release-please with semver tags, so every install path can pin a tag.

The README's first line: "Kubernetes troubleshooting skills for any AI agent: read first,
ask before changing anything." It shows the install paths, the skill list, and the three
tiers.

### Installing one skill instead of all

Every path supports a single skill as well as the whole set:

| Path | One skill | All skills |
|---|---|---|
| Vercel `skills` CLI | `npx skills add k8s-servant/k8s-skills -s k8s-network-troubleshooting` | `npx skills add k8s-servant/k8s-skills` |
| GitHub CLI | `gh skill install k8s-servant/k8s-skills k8s-network-troubleshooting` | `gh skill install k8s-servant/k8s-skills` |
| Claude Code | `/plugin install k8s-network-troubleshooting@k8s-skills` | `/plugin install k8s-skills@k8s-skills` |
| Gemini CLI | `gemini skills install https://github.com/k8s-servant/k8s-skills.git --path skills/k8s-network-troubleshooting` | `gemini extensions install https://github.com/k8s-servant/k8s-skills` |
| Codex | `npx skills add k8s-servant/k8s-skills -s k8s-network-troubleshooting -a codex` | `npx skills add k8s-servant/k8s-skills -a codex` |
| Manual copy | copy `skills/k8s-network-troubleshooting/` | copy `skills/*` |
| claude.ai / API | upload `k8s-network-troubleshooting.zip` from the release | upload each zip |

Skills that hand over to each other (`k8s-triage` names the others) still work alone: a
hand-off to a skill that is not installed tells the agent to continue with the steps in the
current skill and mention which skill would help.

## Testing

Every skill except cloud skills has scenarios in `tests/<skill>/<case>/`:

- `setup.sh`: creates what the case needs on a kind cluster (its own kubeconfig, never the
  user's current context).
- `break.sh`: breaks it the way it breaks in real life.
- `expected.md`, fixed sections: **Prompt** (what the user tells the agent: the symptom
  only, no hint), **Cause** (one sentence), **Evidence** (what the agent
  must point at, e.g. the event reason), **Acceptable fixes**, **Wrong answers** (plausible
  causes that are not it).
- `cleanup.sh`.

A skill is merged only after its scenarios were run with at least one agent and a reviewer
judged that the agent named the Cause (the agent works through a view-only kubeconfig on the
test cluster, so it cannot change anything even by mistake), pointed at the Evidence and proposed an Acceptable
fix. The PR template records each run (agent, model, kind and component versions, result).
**No automated scoring harness in the first release**: judging is manual against
`expected.md`, whose fixed sections keep a harness possible later.

Versions: scenarios target one pinned kind node image (at the start: kind v0.33.0's default,
`kindest/node:v1.37.0` by digest), recorded in `tests/versions.env` and bumped deliberately; `verified-with`
names that version.

kind limits:
- NetworkPolicy scenarios install a CNI that enforces policy (Calico or Cilium) in
  `setup.sh`; kind's default CNI does not enforce it.
- Storage scenarios use the local-path provisioner: PVC Pending (missing or wrong
  StorageClass, unbound), a pod that cannot mount, a volume filling up. CSI attach errors
  are checked against docs only.
- Cluster autoscaler behaviour cannot happen on kind; that part of
  `k8s-node-troubleshooting` is checked against docs only, like cloud skills, and the PR says
  so. Every skill still needs at least two kind scenarios.

CI on every PR (cheap, no model):

- frontmatter: valid YAML, portable fields only, name and description rules, name equals
  folder, `verified-with` present;
- every command outside the allow-list sits in a marked Proposed fix block; Secret access never appears;
- links resolve; markdown lint;
- `claude plugin validate`, and schema checks for the other manifests where a validator exists;
- every non-cloud skill has at least two scenarios, and scenario scripts pass `shellcheck`;
- actionlint, zizmor, gitleaks.

Scenario runs with a model are manual (they cost tokens). Cloud skills are checked against
provider docs and, when a contributor has an account, a real cluster; their PR says which.

## Repository layout

```
skills/<name>/SKILL.md, references/, scripts/
tests/<skill>/<case>/setup.sh, break.sh, expected.md, cleanup.sh
.claude-plugin/marketplace.json
plugin.json (portable agent-plugins manifest)
gemini-extension.json
.github/workflows/ (ci, release-please, release zips)
README.md, CONTRIBUTING.md (skill template + checklist), AGENTS.md, SECURITY.md, LICENSE
docs/design.md (this file)
```

## Changed during implementation

- **Codex** installs through the Vercel CLI: `npx skills add k8s-servant/k8s-skills -a codex`
  (one skill with `-s <name>`, or all). There is no Codex marketplace file until it is
  confirmed that Codex accepts the repository root as a plugin source; the root
  `plugin.json` is kept for that. No `.codex-plugin/` or `.agents/plugins/` folder exists.
- **Markdown is parsed with markdown-it-py** (CommonMark), so what counts as a code block
  follows a real renderer's rules instead of hand-written parsing.
- **The checker is a guardrail for honest mistakes, not a sandbox.** Human review covers
  deliberate obfuscation; CONTRIBUTING lists the known limits.
- **Proposed fix blocks are exempt from every command rule except the Secret ban and the
  `# Undo:` line**, since a human reads and runs them.
- **How users run their agent is their own decision and risk.** The README warns that the
  skills' read-only design is not a 100% guarantee and that the Kubernetes RBAC of the
  agent's credentials is what actually limits it. The skills themselves still only propose
  fixes.
- **Every test case's `expected.md` starts with a Prompt section**: the symptom the user
  gives the agent, with no hint of the cause.
- Gemini CLI and per-skill Claude Code installs follow the tools' documentation but are
  marked "not yet verified" in the README until a real install confirms them.

## Changed after release

- **Read first, ask before changing (after v0.1.1).** A strictly read-only approach cut
  the quality of what the skills can do. What matters is avoiding destructive actions, so
  the maintainer replaced "read-only by default" with three tiers:
  - **Run freely:** the `commands` allow-list.
  - **Ask first:** reversible changes and `exec` of one read-only program, from a
    reviewed `ask_first` allow-list, under
    `> Ask first: the agent runs this only after the user approves it.`, each change with
    an `# Undo:` line.
  - **Never run:** destructive commands, only as proposed fixes for a human.

  "Ask first" is an instruction to the agent, not a lock; RBAC stays the hard limit.
  `port-forward` and `debug` are left out of `ask_first`: one never returns, the other
  adds a container that cannot be removed.
- **Lighter ask-first checks (after #26).** The first ask-first checker also parsed
  the arguments: curl and wget flags, URL schemes, metadata hosts in every address form,
  narrow-change rules. That code grew with each review and checked what the user
  already sees before approving. The checker now checks the verb, the exec program and
  Secret access. Argument rules are a review item in CONTRIBUTING.md.

## Repository creation

The maintainer approves creating the GitHub repository, its settings (branch protection,
required checks, a `release` environment) and the review bot secret. The plan produces the
files and the exact `gh` commands; those commands run only after that approval.

## Left to the builder

- Exact manifest contents and whether each plugin system accepts the repo root as the plugin
  source. If one does not, find a layout that still keeps a single copy of each skill (for
  example a plugin folder that points at `skills/`); do not copy files.
- The CI tooling (Python or shell) and markdown linter.
- How to parse fenced shell lines to apply the allow-list.
- Which scenarios each first-batch skill gets (at least two per skill, covering its most
  common causes).
- Wording of skills, as long as it follows the conventions above.

## Open items

- **Trademark.** "Kubernetes" and "K8s" are Linux Foundation marks; its policy says a mark
  should not be part of a product name. Accepted for now, same as `k8s-servant`; rename both
  if asked. Could be settled by asking trademarks@linuxfoundation.org.
- **Antigravity CLI** (replaced Gemini CLI for some users in 2026-06): skill paths not yet
  checked.
- **Docs site:** after the first batch, if wanted.

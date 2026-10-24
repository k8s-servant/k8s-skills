Kubernetes troubleshooting skills for any AI agent: read first, ask before changing
anything.

k8s-skills is a set of [Agent Skills](https://agentskills.io) that teach an AI agent to
investigate Kubernetes problems the way an experienced SRE does: what to look at, in
which order, what each finding means, and what to propose. The skills work in Claude
Code, Codex, Gemini CLI, GitHub Copilot and any other agent that reads `SKILL.md`
files and can run `kubectl`.

## Read first, ask before changing

Every command in a skill falls into one of three tiers. CI checks each one against the
allow-lists in `tools/skillcheck/allowlist.yaml`.

| Tier | What | What the agent does |
|---|---|---|
| Run freely | Read-only commands: `get`, `describe`, `logs`, `events`, `top` and a short list of others | Runs them while it investigates |
| Ask first | Reversible changes (`set image`, `set resources`, `rollout undo`, `scale`, `patch`, `cordon`, `uncordon` and a few more) and one read-only program run in a container with `exec` (`nslookup`, `curl`, `cat`, ...) | Shows the command, what it changes and how to undo it, under `> Ask first: the agent runs this only after the user approves it.`, and runs it only after you say yes |
| Never run | Anything destructive or hard to undo (`delete`, `drain`, `replace`, `apply`, ...) | Proposes it under `> Proposed fix: review before running. The agent does not run this.`, with an `# Undo:` line, for you to review and run |

Secrets are never read, in any tier. Every change, in either tier, comes with an
`# Undo:` line.

## Your agent, your decision

How you run your agent, and with which permissions, is your decision and your risk. The
skills are written and checked to keep to these tiers, but that is not a 100% guarantee:
"ask first" is an instruction the agent follows, not a lock, and an agent in an
auto-approve mode may not stop to ask. What actually limits an agent is the Kubernetes
RBAC of the credentials you give it. If you want it to only investigate, give it a
read-only identity, for example one bound to the built-in `view` ClusterRole. `view`
cannot read cluster-scoped objects, so for `k8s-triage` on a whole cluster and for the
node and storage skills also allow `get`, `list` and `watch` on `nodes`,
`persistentvolumes`, and in `storage.k8s.io` on `storageclasses`, `csidrivers`,
`csinodes` and `volumeattachments`. Give it more only if you want it to apply the changes you approve (see [Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)).

## Skills

| Skill | Use it when |
|---|---|
| `k8s-triage` | Something is wrong in the cluster and it is not clear where: a ranked first look at nodes, pods, events and resource use, with a first fix and the skill that goes deeper |
| `k8s-workload-troubleshooting` | A pod or workload is unhealthy: Pending, CrashLoopBackOff, image pull errors, OOMKilled, failing probes, stuck rollouts, failing Jobs |
| `k8s-network-troubleshooting` | Traffic does not reach running pods: Services without endpoints, wrong selectors or ports, DNS, NetworkPolicies, Ingress and Gateway routes |
| `k8s-storage-troubleshooting` | Storage blocks a workload: PVCs stuck Pending, missing StorageClasses or unsupported access modes, attach and mount errors, full volumes |
| `k8s-node-troubleshooting` | A node is NotReady or under pressure, or pods will not go onto it: taints, cordoned nodes, requests that do not fit, an autoscaler that does not scale |

Planned: ecosystem and cloud skills.

## Install

Install with the [`skills` CLI](https://github.com/vercel-labs/skills), or copy the
folders yourself. Both work for one skill or all of them.

```bash
# All skills, for Claude Code (use -a codex, ... for other agents)
npx skills add k8s-servant/k8s-skills -a claude-code

# One skill
npx skills add k8s-servant/k8s-skills -s k8s-triage -a claude-code
```

The CLI sends anonymous usage telemetry; set `DISABLE_TELEMETRY=1` to turn it off.

Or copy from a clone of this repository:

```bash
git clone https://github.com/k8s-servant/k8s-skills.git
mkdir -p .claude/skills && cp -R k8s-skills/skills/* .claude/skills/
```

Copy into `~/.claude/skills` instead to have the skills in every project. Other agents
read `.agents/skills` (Codex, Gemini CLI, GitHub Copilot) or `.github/skills` (GitHub
Copilot).

### Other ways

- **Claude Code plugin:** `/plugin marketplace add k8s-servant/k8s-skills`, then
  `/plugin install k8s-skills@k8s-skills` for all skills or
  `/plugin install k8s-triage@k8s-skills` for one.
- **GitHub CLI** (preview): `gh skill install k8s-servant/k8s-skills --all`, or one skill
  by name, pinned with `@vX.Y.Z`.
- **Gemini CLI:** `gemini extensions install https://github.com/k8s-servant/k8s-skills`
  for all skills. Gemini reads project skills only in a folder you have trusted.

Skills that hand over to each other still work alone: a hand-off to a skill that is not
installed tells the agent to continue with the steps it has and name the skill that would
help.

## Contributing

New skills and fixes are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first. Report
security problems as described in [SECURITY.md](SECURITY.md).

## License

[Apache-2.0](LICENSE)

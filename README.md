Kubernetes troubleshooting skills for any AI agent: read first, ask before changing
anything.

k8s-skills is a set of [Agent Skills](https://agentskills.io) that teach an AI agent to
investigate Kubernetes problems the way an experienced SRE does: what to look at, in
which order, what each finding means, and what to propose. The skills work in Claude
Code, Codex, Gemini CLI, GitHub Copilot, Cursor and any other agent that reads
`SKILL.md` files.

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
cannot read nodes, so for `k8s-triage` on a whole cluster and for
`k8s-node-troubleshooting` also allow `get`, `list` and `watch` on `nodes`. Give it more
only if you want it to apply the changes you approve (see [Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)).

## Skills

| Skill | Use it when |
|---|---|
| `k8s-triage` | Something is wrong in the cluster and it is not clear where: a ranked first look at nodes, pods, events and resource use, with a first fix and the skill that goes deeper |
| `k8s-workload-troubleshooting` | A pod or workload is unhealthy: Pending, CrashLoopBackOff, image pull errors, OOMKilled, failing probes, stuck rollouts, failing Jobs |
| `k8s-network-troubleshooting` | Traffic does not reach running pods: Services without endpoints, wrong selectors or ports, DNS, NetworkPolicies, Ingress and Gateway routes |
| `k8s-node-troubleshooting` | A node is NotReady or under pressure, or pods will not go onto it: taints, cordoned nodes, requests that do not fit, an autoscaler that does not scale |

Planned: `k8s-storage-troubleshooting`, then ecosystem and cloud skills.

## Install

The examples use `k8s-workload-troubleshooting`. Every path can install one skill or all
of them.

### Installing one skill instead of all

| Path | One skill | All skills |
|---|---|---|
| Vercel `skills` CLI | `npx skills add k8s-servant/k8s-skills -s k8s-workload-troubleshooting` | `npx skills add k8s-servant/k8s-skills` |
| GitHub CLI (preview) | `gh skill install k8s-servant/k8s-skills k8s-workload-troubleshooting` | `gh skill install k8s-servant/k8s-skills --all` |
| Claude Code | `/plugin install k8s-workload-troubleshooting@k8s-skills` | `/plugin install k8s-skills@k8s-skills` |
| Gemini CLI | `gemini skills install https://github.com/k8s-servant/k8s-skills.git --path skills/k8s-workload-troubleshooting` | `gemini extensions install https://github.com/k8s-servant/k8s-skills` |
| Codex | `npx skills add k8s-servant/k8s-skills -s k8s-workload-troubleshooting -a codex` | `npx skills add k8s-servant/k8s-skills -a codex` |
| Manual copy | copy `skills/k8s-workload-troubleshooting/` | copy `skills/*` |
| claude.ai / API (not yet verified\*) | upload `k8s-workload-troubleshooting.zip` from a release | upload each zip |

\* Not yet verified: these paths follow the tools' documentation but have not been
confirmed by a real install. Please open an issue if one does not work for you. The
other paths have been confirmed by a real install.

Notes per path:

- **Claude Code:** add the marketplace first with `/plugin marketplace add k8s-servant/k8s-skills`.
- **Vercel `skills` CLI:** it sends anonymous usage telemetry. Set `DISABLE_TELEMETRY=1`
  to turn it off.
- **GitHub CLI:** `gh skill` is a preview feature. Pin a release with
  `gh skill install k8s-servant/k8s-skills k8s-workload-troubleshooting@vX.Y.Z`. Without
  a skill name or `--all`, it asks which skills to install, or only lists them when it
  is not run in a terminal.
- **Codex:** there is no Codex plugin marketplace file in this repository yet, so Codex
  uses the Vercel CLI with `-a codex`.
- **Gemini CLI:** `gemini skills install` installs for your user by default
  (`--scope workspace` for the current project). The extension installs every skill.
- **Manual copy:** put the folder into `.agents/skills`, `.claude/skills`,
  `.github/skills` or `.cursor/skills` (in a project, or in your home directory for all
  projects). `.cursor/skills` is not yet verified\*. Gemini CLI reads project skills
  only in a folder you have trusted.
- **claude.ai and the API:** each GitHub release has one zip per skill. Upload it in the
  skills settings, or through the API.

Skills that hand over to each other still work alone: a hand-off to a skill that is not
installed tells the agent to continue with the steps it has and name the skill that would
help.

## Contributing

New skills and fixes are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first. Report
security problems as described in [SECURITY.md](SECURITY.md).

## License

[Apache-2.0](LICENSE)

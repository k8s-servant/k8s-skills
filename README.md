Read-only Kubernetes skills for any AI agent.

k8s-skills is a set of [Agent Skills](https://agentskills.io) that teach an AI agent to
investigate Kubernetes problems the way an experienced SRE does: what to look at, in
which order, what each finding means, and what to propose. The skills work in Claude
Code, Codex, Gemini CLI, GitHub Copilot, Cursor and any other agent that reads
`SKILL.md` files.

## What read-only means

The agent investigates; fixes are proposed, never run.

- Every command a skill tells the agent to run is read-only (`get`, `describe`, `logs`,
  `events`, `top` and a short list of others). CI rejects anything that is not on the
  allow-list in `tools/skillcheck/allowlist.yaml`.
- Secrets are never read. No skill shows `get`, `describe` or a listing of Secrets in any
  form.
- A fix appears only as a **proposed fix** under the line
  `> Proposed fix: review before running. The agent does not run this.`, with an
  `# Undo:` line. A human reviews it and runs it.

## Your agent, your decision

How you run your agent, and with which permissions, is your decision and your risk. The
skills are written and checked to be read-only, but that is not a 100% guarantee: an
agent can misread a skill or act on its own. What actually limits an agent is the
Kubernetes RBAC of the credentials you give it. If you want a hard limit, run the agent
with a read-only identity, for example one bound to the built-in `view` ClusterRole
(see [Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)).

## Skills

| Skill | Use it when |
|---|---|
| `k8s-workload-troubleshooting` | A pod or workload is unhealthy: Pending, CrashLoopBackOff, image pull errors, OOMKilled, failing probes, stuck rollouts, failing Jobs |

Planned: `k8s-triage` (something is wrong and it is not clear where),
`k8s-node-troubleshooting`, `k8s-network-troubleshooting`, `k8s-storage-troubleshooting`,
then ecosystem and cloud skills.

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
other paths were installed from the v0.1.0 release.

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
  projects). `.github/skills` and `.cursor/skills` are not yet verified\*. Gemini CLI
  reads project skills only in a folder you have trusted.
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

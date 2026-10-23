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

This is a guardrail against honest mistakes in the skills, not a sandbox. The guarantee
you can rely on is the one you set up yourself, in the next section.

## Run your agent read-only (recommended)

Run the agent with credentials that cannot change anything. Then no instruction, in a
skill or anywhere else, can modify the cluster. This is the guarantee to rely on; the
read-only design of the skills is a layer on top of it.

Create a ServiceAccount bound to the built-in ClusterRole `view` (it cannot read Secrets
and cannot change anything), and build a kubeconfig that uses its token. These commands
create objects, so run them yourself, once, as a cluster admin, and replace the
placeholders:

```bash
# Example setup, run by you (not by the agent). Creates a ServiceAccount and a binding.
kubectl create serviceaccount agent-readonly -n my-namespace
kubectl create clusterrolebinding agent-readonly-view \
  --clusterrole=view --serviceaccount=my-namespace:agent-readonly

# Short-lived token (here 8 hours) and a kubeconfig that uses it.
TOKEN=$(kubectl create token agent-readonly -n my-namespace --duration=8h)
kubectl config set-cluster my-cluster --server=https://my-cluster.example.com:6443 \
  --certificate-authority=ca.crt --embed-certs=true --kubeconfig=agent.kubeconfig
kubectl config set-credentials agent-readonly --token="$TOKEN" --kubeconfig=agent.kubeconfig
kubectl config set-context agent-readonly --cluster=my-cluster --user=agent-readonly \
  --kubeconfig=agent.kubeconfig
kubectl config use-context agent-readonly --kubeconfig=agent.kubeconfig
```

Start the agent with `KUBECONFIG=agent.kubeconfig`. The token expires on its own; create
a new one when you need it. The API server may cap how long a token can live, so the
token you get can be shorter than `--duration` asks for. Treat `agent.kubeconfig` as a
credential and do not commit it.

`ca.crt` is the cluster's CA certificate. You can take it from your own kubeconfig:
`kubectl config view --raw --minify -o jsonpath='{.clusters[0].cluster.certificate-authority-data}' | base64 -d > ca.crt`.

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
| GitHub CLI (preview) | `gh skill install k8s-servant/k8s-skills k8s-workload-troubleshooting` | `gh skill install k8s-servant/k8s-skills` |
| Claude Code | `/plugin install k8s-workload-troubleshooting@k8s-skills` (not yet verified\*) | `/plugin install k8s-skills@k8s-skills` |
| Gemini CLI (not yet verified\*) | `gemini skills install https://github.com/k8s-servant/k8s-skills.git --path skills/k8s-workload-troubleshooting` | `gemini extensions install https://github.com/k8s-servant/k8s-skills` |
| Codex | `npx skills add k8s-servant/k8s-skills -s k8s-workload-troubleshooting -a codex` | `npx skills add k8s-servant/k8s-skills -a codex` |
| Manual copy | copy `skills/k8s-workload-troubleshooting/` | copy `skills/*` |
| claude.ai / API | upload `k8s-workload-troubleshooting.zip` from a release | upload each zip |

\* Not yet verified: these paths follow the tools' documentation but have not been
confirmed by a real install. Please open an issue if one does not work for you.

Notes per path:

- **Claude Code:** add the marketplace first with `/plugin marketplace add k8s-servant/k8s-skills`.
- **Vercel `skills` CLI:** it sends anonymous usage telemetry. Set `DISABLE_TELEMETRY=1`
  to turn it off.
- **GitHub CLI:** `gh skill` is a preview feature. Pin a release with
  `gh skill install k8s-servant/k8s-skills k8s-workload-troubleshooting@vX.Y.Z`.
- **Codex:** there is no Codex plugin marketplace file in this repository yet, so Codex
  uses the Vercel CLI with `-a codex`.
- **Manual copy:** put the folder into `.agents/skills`, `.claude/skills`,
  `.github/skills` or `.cursor/skills` (in a project, or in your home directory for all
  projects).
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

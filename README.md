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
`csinodes` and `volumeattachments`. `view` cannot read RBAC objects either, so for
`k8s-rbac-troubleshooting` allow `get` and `list` on `roles`, `rolebindings`,
`clusterroles` and `clusterrolebindings`. Give it more only if you want it to apply the changes you approve (see [Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)).

## Skills

| Skill | Use it when |
|---|---|
| `k8s-triage` | Something is wrong in the cluster and it is not clear where: a ranked first look at nodes, pods, events and resource use, with a first fix and the skill that goes deeper |
| `k8s-workload-troubleshooting` | A pod or workload is unhealthy: Pending, CrashLoopBackOff, image pull errors, OOMKilled, failing probes, stuck rollouts, failing Jobs |
| `k8s-network-troubleshooting` | Traffic does not reach running pods: Services without endpoints, wrong selectors or ports, DNS, NetworkPolicies, Ingress and Gateway routes |
| `k8s-storage-troubleshooting` | Storage blocks a workload: PVCs stuck Pending, missing StorageClasses or unsupported access modes, attach and mount errors, full volumes |
| `k8s-autoscaling-troubleshooting` | Autoscaling does not scale: HPA targets `<unknown>` (missing requests, no metrics), stuck at `maxReplicas`, metrics-server and `kubectl top`, KEDA ScaledObjects not Ready or without an HPA, the VPA |
| `k8s-cert-manager-troubleshooting` | cert-manager does not issue or renew: Certificates not Ready, issuers not Ready, a wrong `issuerRef`, ACME challenges stuck, the cert-manager webhook unreachable |
| `k8s-flux-troubleshooting` | Flux does not deploy: sources not Ready (missing branch, credentials, chart version), Kustomizations with a wrong path or failed build, HelmReleases stalled, suspended objects |
| `k8s-argocd-troubleshooting` | Argo CD does not deploy: comparison errors (wrong path or revision), destinations not allowed by the project, no automated sync, failed syncs, drift, health |
| `k8s-helm-troubleshooting` | Helm installs or upgrades fail or a release is stuck: `--wait` timeouts, ownership conflicts, `another operation is in progress`, hooks, immutable fields; helm commands are left to the user |
| `k8s-kyverno-troubleshooting` | Kyverno denies or fails to police resources: Enforce denials, Audit-only policies and PolicyReports, ClusterPolicy and CEL ValidatingPolicy, mutate and generate rules, webhooks down |
| `k8s-gatekeeper-troubleshooting` | OPA Gatekeeper denies or fails to police resources: constraint denials and actions, templates that do not compile, a webhook that fails open, exemptions, sync, mutation |
| `k8s-external-secrets-troubleshooting` | External Secrets does not create or update a Secret: sync errors from the controller log, stores not Ready, targets owned by another ExternalSecret, refresh; never reads the Secrets |
| `k8s-prometheus-troubleshooting` | Prometheus does not scrape or alert: ServiceMonitors not selected, wrong port names, targets down, rules not loaded, alerts not reaching Alertmanager, memory and disk |
| `k8s-grafana-troubleshooting` | Grafana fails: provisioning errors that crash the pod, dashboards that do not load, datasources pointing at the wrong Service, database locks, login, grafana-operator selectors |
| `k8s-cilium-troubleshooting` | Traffic fails on a Cilium cluster: CiliumNetworkPolicy drops and default deny, DNS blocked by egress policies, L7 403s, Hubble flows, agent, endpoint and IPAM problems |
| `k8s-istio-troubleshooting` | Requests fail in an Istio mesh: Envoy access logs and response flags (UH, NR, filter_chain_not_found), AuthorizationPolicy 403s, subsets without pods, STRICT mTLS, injection, ambient |
| `k8s-envoy-gateway-troubleshooting` | Envoy Gateway does not route: Gateways not Programmed, HTTPRoutes not Accepted (hostnames, allowedRoutes), unresolved backends and missing ReferenceGrants, 404/500/503, policies |
| `k8s-rbac-troubleshooting` | A request is refused: `Forbidden`, `cannot list resource ... in the namespace` or `at the cluster scope`, bindings in the wrong namespace or for the wrong subject, ClusterRoles bound with RoleBindings, 401 versus 403, escalation and `roleRef` errors |
| `k8s-node-troubleshooting` | A node is NotReady or under pressure, or pods will not go onto it: taints, cordoned nodes, requests that do not fit, an autoscaler that does not scale |

Planned: cloud skills (AKS, EKS, GKE) and more ecosystem skills.

## How each skill is verified

A skill is merged only after four checks:

1. **Official sources.** Facts come from the project's own documentation and, where the
   docs are silent, its source code at the release named below. Each skill lists the
   pages and files in its `Sources` section.
2. **A real cluster.** Every status message, log line and response a skill quotes was
   reproduced on a throwaway [kind](https://kind.sigs.k8s.io) cluster, with the tool
   installed at a pinned version whose checksum is verified first (`tests/versions.env`).
   Where the cluster printed something different from the docs, the skill quotes the
   cluster.
3. **Scenarios run by an agent.** Each scenario in `tests/<skill>/<case>/` breaks
   something on purpose, and its `expected.md` names the cause, the evidence, the
   acceptable fixes and the wrong answers. A fresh agent gets the skill, the prompt and a
   view-only kubeconfig, and passes only if it names the cause, points at the evidence,
   proposes an acceptable fix and changes nothing. The runs are recorded in the skill's
   pull request.
4. **CI on every change.** `skillcheck` checks each command against its tier, the
   ask-first and fix blocks, the `# Undo:` lines and that no command reads Secrets; tests,
   linters and a link check run as well.

| Skill | Verified with | Scenarios |
|---|---|---|
| `k8s-argocd-troubleshooting` | kubernetes 1.37, argo-cd 3.5 | `app-path-missing`, `auto-sync-off`, `project-destination-denied` |
| `k8s-autoscaling-troubleshooting` | kubernetes 1.37, metrics-server 0.9, keda 2.21 | `keda-target-wrong`, `max-replicas-reached`, `missing-cpu-request` |
| `k8s-cert-manager-troubleshooting` | kubernetes 1.37, cert-manager 1.21 | `ca-issuer-missing-key-pair`, `cluster-issuer-kind-missing`, `webhook-down` |
| `k8s-cilium-troubleshooting` | kubernetes 1.37, cilium 1.20 | `egress-policy-blocks-dns`, `ingress-policy-wrong-label`, `l7-rule-denies-path` |
| `k8s-envoy-gateway-troubleshooting` | kubernetes 1.37, envoy-gateway 1.9, gateway-api 1.6 | `backend-not-found`, `cross-namespace-no-referencegrant`, `hostname-mismatch` |
| `k8s-external-secrets-troubleshooting` | kubernetes 1.37, external-secrets 2.14 | `provider-key-missing`, `store-name-wrong`, `target-owned-by-other` |
| `k8s-flux-troubleshooting` | kubernetes 1.37, flux 2.9 | `git-branch-missing`, `helm-chart-version-missing`, `kustomization-path-missing` |
| `k8s-gatekeeper-troubleshooting` | kubernetes 1.37, gatekeeper 3.23 | `constraint-denies-deployment`, `template-rego-error`, `webhook-down-fails-open` |
| `k8s-grafana-troubleshooting` | kubernetes 1.37, grafana 13.2 | `dashboard-json-invalid`, `datasource-two-defaults`, `datasource-url-wrong` |
| `k8s-helm-troubleshooting` | kubernetes 1.37, helm 4.3 | `ownership-conflict`, `release-stuck-pending`, `upgrade-timeout-bad-image` |
| `k8s-istio-troubleshooting` | kubernetes 1.37, istio 1.31 | `authorizationpolicy-denies`, `strict-mtls-plaintext-client`, `subset-without-pods` |
| `k8s-kyverno-troubleshooting` | kubernetes 1.37, kyverno 1.19 | `audit-does-not-block`, `enforce-blocks-deployment`, `validatingpolicy-denies` |
| `k8s-network-troubleshooting` | kubernetes 1.37, gateway-api 1.6 | `networkpolicy-blocks-namespace`, `selector-mismatch`, `wrong-target-port` |
| `k8s-node-troubleshooting` | kubernetes 1.37 | `node-not-ready`, `requests-full`, `untolerated-taint` |
| `k8s-prometheus-troubleshooting` | kubernetes 1.37, prometheus-operator 0.94, prometheus 3.14 | `servicemonitor-not-selected`, `servicemonitor-port-name-wrong`, `target-path-404` |
| `k8s-rbac-troubleshooting` | kubernetes 1.37 | `clusterrole-bound-in-namespace`, `role-missing-verb`, `subject-namespace-wrong` |
| `k8s-storage-troubleshooting` | kubernetes 1.37 | `missing-storageclass`, `unsupported-access-mode`, `waiting-for-first-consumer` |
| `k8s-triage` | kubernetes 1.37 | `crashloop-somewhere`, `healthy-cluster`, `namespace-only-access`, `node-not-ready` |
| `k8s-workload-troubleshooting` | kubernetes 1.37 | `image-pull-wrong-tag`, `oom-killed`, `readiness-probe-failing` |

`verified-with` and `verified-on` in each `SKILL.md` record the same versions and the
date. Other versions usually behave the same, but messages and defaults can change
between releases. kind cannot reproduce cloud-only behaviour (load balancers, cloud
storage, managed node pools), so those parts are checked against the docs only. To run
a scenario yourself, see [Scenarios and the test kit](CONTRIBUTING.md#scenarios-and-the-test-kit).

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

Or copy from a clone of this repository. Into your home directory, the skills are
available in every project:

```bash
git clone https://github.com/k8s-servant/k8s-skills.git ~/k8s-skills
mkdir -p ~/.claude/skills && cp -R ~/k8s-skills/skills/* ~/.claude/skills/
```

For one project only, copy into the project instead, from its root folder:

```bash
mkdir -p .claude/skills && cp -R ~/k8s-skills/skills/* .claude/skills/
```

In a project, other agents read `.agents/skills` (Codex, Gemini CLI, GitHub Copilot) or
`.github/skills` (GitHub Copilot).

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

New skills and fixes are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) first. What
runs on each pull request is described in [docs/ci.md](docs/ci.md). Report
security problems as described in [SECURITY.md](SECURITY.md).

## License

[Apache-2.0](LICENSE)

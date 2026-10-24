# Comparison errors: Argo CD cannot render the manifests

Before it can compare or sync, the repo-server must fetch the repository at
`spec.source.targetRevision` and render `spec.source.path` (plain YAML, Kustomize, Helm
or a plugin). When that fails, the Application gets a `ComparisonError` condition and
its sync status is `Unknown`; what is already in the cluster keeps running.

## Investigate

```bash
kubectl get application my-app -n argocd -o jsonpath='{.status.conditions}{"\n"}'
kubectl get application my-app -n argocd -o jsonpath='{.spec.source}{"\n"}{.spec.sources}{"\n"}'
kubectl logs -n argocd deployment/argocd-repo-server --tail=200 | grep -i error
kubectl get configmap argocd-cm -n argocd -o yaml
```

`spec.sources` (plural) is used by multi-source Applications; the error message then
says which source failed (`source 1 of 2`).

## Read the results

The message starts with `Failed to load target state: failed to generate manifest for
source 1 of 1: rpc error: code = Unknown desc =` and ends with the cause:

| End of the message | Meaning |
|---|---|
| `<path>: app path does not exist` | `spec.source.path` is not a folder at that revision. Paths are relative to the repository root. |
| `unable to resolve '<rev>' to a commit SHA` | `targetRevision` names a branch, tag or commit that does not exist. |
| `authentication required`, `repository not found`, `permission denied` | The repository needs credentials Argo CD does not have, or they are wrong. They live in Secrets: the user checks them. |
| A Helm error (`chart ... not found`, `template: ...`) | The chart version, the repository or the values are wrong; the Helm message says which. |
| A Kustomize error (`accumulating resources`, `ID conflict`) | The kustomization in that folder does not build. |
| `Manifest generation error (cached)` | Argo CD caches a failed render; after a fix, a hard refresh (`argocd.argoproj.io/refresh=hard`) renders again. |

A repository that is not in the project's `sourceRepos` gives an `InvalidSpecError`
instead: see [projects-and-destinations.md](projects-and-destinations.md).

## Proposed fix

Fix `path`, `targetRevision` or the chart in the source of the Application (Git, an
ApplicationSet template, or a Helm chart for Argo CD). To test before the Git change,
patch the live Application (ask first, see the main skill). Credentials are for the
user; never read the repository Secrets.

# Sources: GitRepository, OCIRepository, HelmRepository, HelmChart

source-controller fetches each source on its `interval` and stores the result as an
artifact. `status.artifact.revision` is what it last fetched; `Ready` says whether the
last fetch worked. A failed fetch keeps the last good artifact (`ArtifactInStorage`
stays `True`), so the cluster keeps running the old version.

## Investigate

```bash
kubectl get gitrepositories,ocirepositories,helmrepositories,helmcharts,buckets -A
kubectl describe gitrepository my-app -n flux-system
kubectl get gitrepository my-app -n flux-system -o jsonpath='{.spec.url}{"\n"}{.spec.ref}{"\n"}{.spec.secretRef}{"\n"}{.status.artifact.revision}{"\n"}'
kubectl describe helmchart flux-system-my-app -n flux-system
kubectl get helmrepository -n flux-system -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.type}{" "}{.spec.url}{"\n"}{end}'
kubectl events -n flux-system --for gitrepository/my-app
kubectl logs -n flux-system deployment/source-controller --tail=100 | grep my-app
```

`spec.secretRef` shows only the name of the credentials Secret; do not read the Secret.

## Read the results

| Object, reason | Message | Meaning |
|---|---|---|
| GitRepository, `GitOperationFailed` | `failed to checkout and determine revision: unable to clone '<url>': couldn't find remote ref "refs/heads/<branch>"` | The branch (or tag, `refs/tags/...`) in `spec.ref` does not exist. Compare with the repository's real branches. |
| GitRepository, `GitOperationFailed` | `... authentication required`, `authorization failed` or `repository not found` | The credentials in `spec.secretRef` are missing, wrong or lack access, or the URL is wrong. Private repositories often answer "not found" instead of "forbidden". |
| GitRepository, `AuthenticationFailed` | (credential setup error) | The Secret named in `spec.secretRef` is missing or has the wrong keys. Ask the user. |
| any source, `URLInvalid` (`Stalled`) | `failed to parse url ...` | A typo in `spec.url`; Flux will not retry until it changes. |
| HelmChart, `InvalidChartReference` (`Stalled`) | `invalid chart reference: failed to get chart version for remote reference: no '<chart>' chart with version matching '<version>' found` | An HTTP Helm repository has no such chart or version. Compare with the versions the repository publishes. |
| HelmChart, `ChartPullError` | `chart pull error: ... could not locate a version matching provided version string ...` | The same for an OCI repository; this one is retried. |
| HelmRepository not Ready | (fetch error) | The repository URL or its credentials; for OCI (`spec.type: oci`) the repository is not fetched itself, only the chart. |

## Proposed fix

Fix `spec.ref`, `spec.url` or the chart `version` in Git, where the source is defined.
Credentials are for the user to fix; never read or create the Secret yourself. To check
a fix quickly, ask Flux to reconcile the source now (ask first, see the main skill).

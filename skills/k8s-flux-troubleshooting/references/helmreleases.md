# HelmReleases

helm-controller creates a HelmChart for each HelmRelease (named `<namespace>-<name>`),
waits for source-controller to fetch the chart, then installs or upgrades the release
with Helm. Helm stores the release in a Secret: never read it, and never use
`flux debug helmrelease --show-values`, which prints values from Secrets.

## Investigate

```bash
kubectl get helmreleases -A
kubectl describe helmrelease my-app -n flux-system
kubectl get helmrelease my-app -n flux-system -o jsonpath='{.spec.chart}{"\n"}{.spec.chartRef}{"\n"}{.spec.targetNamespace}{"\n"}{.status.conditions}{"\n"}'
kubectl get helmrelease my-app -n flux-system -o jsonpath='{.status.history}{"\n"}'
kubectl describe helmchart flux-system-my-app -n flux-system
kubectl events -n flux-system --for helmrelease/my-app
kubectl logs -n flux-system deployment/helm-controller --tail=100 | grep my-app
```

`status.history` lists the last Helm releases Flux made (chart version, status, digest),
without reading the release Secrets.

## Read the results

| Condition, reason | Message | Meaning |
|---|---|---|
| Ready `SourceNotReady` | `HelmChart '<ns>/<name>' is not ready: ...` | The chart could not be fetched. Read the HelmChart ([sources.md](sources.md)). |
| Ready `ArtifactFailed` | `could not get Source object: ...` | `spec.chart.spec.sourceRef` or `spec.chartRef` names a source that does not exist. |
| Released `InstallFailed` / `UpgradeFailed` | `Helm install failed for release <ns>/<name> with chart <chart>@<version>: ...` | Helm itself failed. The text after the colon is Helm's error: a timeout waiting for resources, a failed hook, an object owned by another release, an immutable field. |
| Stalled `RetriesExceeded` | `Failed to install after N attempt(s)` | The retries in `spec.install.remediation` or `spec.upgrade.remediation` are used up (install retries default to 0). Flux does nothing more until the spec changes or the release is reset. |
| Stalled `MissingRollbackTarget` | | Remediation wanted to roll back, but there is no earlier release. |
| `Remediated` | | Flux rolled back or uninstalled after a failure; the release now runs an older version. |
| `Drifted` | | Someone changed the release's objects in the cluster; Flux corrects drift if `spec.driftDetection` is on. |

For Helm errors in the message, the Helm side is in `k8s-helm-troubleshooting`. The
objects of a release are labelled `app.kubernetes.io/managed-by: Helm` and carry the
annotation `meta.helm.sh/release-name`, so they can be found with kubectl in the target
namespace.

## Proposed fix

Fix the chart version, the values or the remediation settings in Git. After a fix,
a Stalled release starts again by itself because the spec changed. To retry an
unchanged release after its cause was fixed outside Flux, the user can reset it:

> Proposed fix: review before running. The agent does not run this.

```bash
flux reconcile helmrelease my-app -n flux-system --reset
# Undo: none; it only clears the failure counters and runs the release again
```

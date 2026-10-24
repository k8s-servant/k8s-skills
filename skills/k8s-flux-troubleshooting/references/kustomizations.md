# Kustomizations

kustomize-controller takes the artifact of `spec.sourceRef`, builds `spec.path` with
kustomize, applies the result with server-side apply, prunes what was removed (if
`spec.prune`), and waits for health checks (if `spec.wait` or `spec.healthChecks`).
`status.lastAppliedRevision` is the source revision it last applied.

## Investigate

```bash
kubectl get kustomizations -A
kubectl describe kustomization my-app -n flux-system
kubectl get kustomization my-app -n flux-system -o jsonpath='{.spec.sourceRef}{"\n"}{.spec.path}{"\n"}{.spec.dependsOn}{"\n"}{.status.lastAppliedRevision}{"\n"}{.status.lastAttemptedRevision}{"\n"}'
kubectl events -n flux-system --for kustomization/my-app
kubectl logs -n flux-system deployment/kustomize-controller --tail=100 | grep my-app
```

## Read the results

| Ready reason | Message | Meaning |
|---|---|---|
| `ArtifactFailed` | `Source artifact not found, retrying in 30s` | The source has no artifact. Read the source ([sources.md](sources.md)). |
| `ArtifactFailed` | `unable to get source '<ns>/<name>': ... not found` | `spec.sourceRef` names a source that does not exist (name, kind or namespace). |
| `ArtifactFailed` | `kustomization path not found: stat ...` | `spec.path` is not in the artifact. Paths are relative to the repository root. |
| `BuildFailed` | `kustomize build failed: ...` | kustomize itself fails: a missing file in `kustomization.yaml`, duplicate resources (`ID conflict`), a bad patch. |
| `ReconciliationFailed` | (apply error) | The API server refused an object: a missing CRD, an admission webhook or policy, an immutable field. |
| `DependencyNotReady` | `dependency '<ns>/<name>' is not ready` | A Kustomization in `spec.dependsOn` is not Ready. Fix that one first. |
| `HealthCheckFailed` (also on `Healthy`) | `timeout waiting for: [Deployment/<ns>/<name> status: 'InProgress']` | Flux applied the objects, but they did not become ready in time. The workload is the problem: continue with `k8s-workload-troubleshooting`. |
| `PruneFailed` | (delete error) | Flux could not delete a removed object (finalizer, permissions). |

- `lastAttemptedRevision` newer than `lastAppliedRevision`: Flux tried the new commit
  and failed; the cluster still runs the older one.
- Both equal to an old commit while the source has a newer one: Flux has not tried yet;
  the Kustomization is suspended, waits for a dependency, or its `interval` has not
  passed.
- An object that keeps changing back after a manual edit: Flux applies Git over it.
  That is the intended behaviour.

## Proposed fix

Fix the path, the `kustomization.yaml` or the manifests in Git. A patch on the live
Kustomization only lasts until its parent applies Git again (see the main skill). For
health check timeouts, fix the workload, not Flux.

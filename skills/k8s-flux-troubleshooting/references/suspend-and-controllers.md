# Suspended objects, old APIs and the controllers

When nothing happens at all (no new conditions, no events), Flux is not looking at the
object: it is suspended, it uses an API version this Flux no longer serves, or the
controller for it is down.

## Investigate

```bash
kubectl get kustomizations,helmreleases,gitrepositories,ocirepositories,helmrepositories -A -o custom-columns=KIND:.kind,NAMESPACE:.metadata.namespace,NAME:.metadata.name,SUSPENDED:.spec.suspend
kubectl get deployments -n flux-system
kubectl get pods -n flux-system -o wide
kubectl get crds -o custom-columns=NAME:.metadata.name,SERVED:.spec.versions[*].name | grep fluxcd
kubectl logs -n flux-system deployment/kustomize-controller --tail=50
```

## Read the results

- **`SUSPENDED` `true`**: someone ran `flux suspend` or set `spec.suspend: true`, often
  during an incident or a migration. The conditions are those of the last run before.
  Ask why before resuming it.
- **Manifests on removed API versions**: Flux 2.7 removed the `v1beta1` and `v2beta1`
  APIs, 2.8 `v1beta2` and `v2beta2`, 2.9 the image `v1beta2` and notification `v1beta2`
  APIs. Applying them fails with `no matches for kind`; a parent Kustomization shows
  that error. Flux 2.9 serves `source.toolkit.fluxcd.io/v1`,
  `kustomize.toolkit.fluxcd.io/v1`, `helm.toolkit.fluxcd.io/v2` and
  `image.toolkit.fluxcd.io/v1`; `Alert` and `Provider` are still
  `notification.toolkit.fluxcd.io/v1beta3`.
- **A controller not running**: its objects stop changing. source-controller down
  stops every fetch; kustomize-controller or helm-controller down stops applies. For
  crashing or Pending controller pods, continue with `k8s-workload-troubleshooting`.
- **Very slow updates**: each object runs on its own `spec.interval`; a change in Git
  waits up to the source's interval, then the Kustomization's. A webhook `Receiver`
  shortens that, if one is set up.

## Proposed fix

Resume a suspended object (ask first, see the main skill) once the reason is known.
Move manifests to the served API versions in Git. Upgrading Flux itself is for the
user, following the upgrade notes of each release.

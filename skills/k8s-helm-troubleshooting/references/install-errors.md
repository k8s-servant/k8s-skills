# Install errors

Before applying anything, `helm install` checks that the name is free and that no
object it would create already exists outside the release. Those checks fail fast, so
nothing of the release is in the cluster yet.

## Investigate

```bash
kubectl get service my-app-podinfo -n my-namespace -o jsonpath='{.metadata.labels}{"\n"}{.metadata.annotations}{"\n"}{.metadata.creationTimestamp}{"\n"}{.metadata.managedFields[*].manager}{"\n"}'
kubectl get all,configmaps,ingresses -n my-namespace -o jsonpath='{range .items[*]}{.kind}{" "}{.metadata.name}{" "}{.metadata.annotations}{"\n"}{end}'
kubectl get crds
```

`managedFields[*].manager` names the tool that created or changed the object
(`kubectl-create`, `kubectl-client-side-apply`, `helm`, a controller), which says where
it came from.

## Read the results

| Error | Meaning |
|---|---|
| `unable to continue with install: <Kind> "<name>" in namespace "<ns>" exists and cannot be imported into the current release: invalid ownership metadata; label validation error: missing key "app.kubernetes.io/managed-by": must be set to "Helm"; annotation validation error: missing key "meta.helm.sh/release-name": must be set to "<release>"; ...` | The object exists without Helm's ownership marks: created by hand or another tool. Helm 3 starts with "Unable". |
| `... annotation validation error: key "meta.helm.sh/release-name" must equal "<release>": current value is "<other>"` | The object belongs to another release. Two releases render the same name. |
| `cannot reuse a name that is still in use` (Helm 3: `cannot re-use`) | A release of that name already exists, maybe failed or pending. Ask for `helm list`; upgrade it instead, or uninstall it first. |
| `resource mapping not found for name: ... ensure CRDs are installed first` | The chart uses a custom resource whose CRD is not installed (or is installed by this same chart outside `crds/`). |
| `no matches for kind "<Kind>" in version "<group>/<version>"` | An API version this cluster does not serve, for example one removed in a Kubernetes upgrade. |

## Proposed fix

- **Object created by hand, meant to be part of the release**: add the ownership label
  and annotations (ask first, see the main skill), then the user installs again. Helm
  4 can also do this itself with `helm install --take-ownership`, which the user runs.
- **Object that should not be there**: the user deletes it, if nothing else uses it,
  then installs:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl delete service my-app-podinfo -n my-namespace
# Undo: kubectl create service clusterip my-app-podinfo --tcp=9898:9898 -n my-namespace (recreate it as it was, from its YAML)
```

- **Two releases with the same object names**: give one a different release name or
  `fullnameOverride`, in its values.
- **Missing CRDs**: the user installs the CRDs (often a separate chart or the
  operator's manifest) before the chart.
- **Removed APIs**: update the chart to served API versions. For a release that already
  uses a removed API, the user follows the Helm guide on deprecated APIs (the
  `helm-mapkubeapis` plugin).

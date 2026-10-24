# The target Secret, refresh and API versions

`spec.target` controls the Secret ESO writes: its name (default: the ExternalSecret's
name), `creationPolicy` (`Owner` by default: ESO creates the Secret and owns it;
`Orphan`, `Merge`, `CreateOrMerge`, `None`), `deletionPolicy` (`Retain` by default,
`Delete`, `Merge`) and `immutable`.

## Investigate

```bash
kubectl get externalsecrets -n my-namespace -o custom-columns=NAME:.metadata.name,TARGET:.spec.target.name,POLICY:.spec.target.creationPolicy,STATUS:.status.conditions[0].reason
kubectl get externalsecret my-app-config -n my-namespace -o jsonpath='{.spec.refreshInterval}{" "}{.spec.refreshPolicy}{" "}{.status.refreshTime}{" "}{.status.syncedResourceVersion}{"\n"}'
kubectl get clusterexternalsecret my-app-config -o jsonpath='{.status.conditions}{"\n"}{.status.failedNamespaces}{"\n"}{.status.provisionedNamespaces}{"\n"}'
kubectl get crd externalsecrets.external-secrets.io -o jsonpath='{range .spec.versions[*]}{.name}{" served="}{.served}{"\n"}{end}'
```

To see which ExternalSecret wrote a target Secret, compare the ExternalSecrets'
`spec.target.name` values; do not read the Secret.

## Read the results

- **`SecretOwnedByOther`**, `target is owned by another ExternalSecret: ... secret is
  owned by another ExternalSecret: <name>`: two ExternalSecrets have the same target
  name. The first one created the Secret and owns it. Merge their keys into one
  ExternalSecret, give each its own target, or use `creationPolicy: Merge` on purpose.
- **`failed to take ownership of target secret`**: the Secret exists and belongs to
  something else (created by hand or by another controller).
- **`SecretMissing`**, `secret will not be created due to CreationPolicy=Merge`: with
  `Merge` ESO only adds keys to a Secret that already exists.
- **`SecretImmutable`**, `could not update secret, target is immutable`: the target is
  immutable; changed values need a new Secret.
- **Values that do not refresh**: `refreshInterval` (default `1h`; `0s` fetches once),
  `refreshPolicy` `CreatedOnce` or `OnChange`, or a provider version pinned in
  `remoteRef.version`. Pods that read the Secret as environment variables need a
  restart to see new values; mounted files update after a delay.
- **ClusterExternalSecret** with `one or more namespaces failed`: `failedNamespaces`
  says why for each namespace (often an ExternalSecret of the same name already exists
  there).
- **`no matches for kind "ExternalSecret" in version "external-secrets.io/v1beta1"`**:
  `v1beta1` is no longer served (since ESO 0.17). Manifests must use
  `external-secrets.io/v1`.

## Proposed fix

- Duplicate targets: change one ExternalSecret's `spec.target.name`, or combine them, in
  the source. Deleting the other ExternalSecret or its Secret is the user's call:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl delete externalsecret my-app-flags -n my-namespace
# Undo: apply the ExternalSecret my-app-flags again from its source
```

- Old API versions: move manifests to `external-secrets.io/v1` in the source.
- Stale values in pods: restart the workload (ask first, through
  `k8s-workload-troubleshooting`) or let a reloader do it.

# Sync errors: SecretSyncedError

Since ESO 2.14, every store or provider problem gives the same status and event:
`Ready` `False`, reason `SecretSyncedError`, `could not get secret data from provider`
(event reason `UpdateFailed`). Only errors ESO marks safe (ownership, immutability) keep
their detail in the status. Everything else is in the controller's log.

## Investigate

```bash
kubectl get externalsecret my-app-config -n my-namespace -o jsonpath='{.spec.secretStoreRef}{"\n"}{range .spec.data[*]}{.secretKey}{" <- "}{.remoteRef}{"\n"}{end}{.spec.dataFrom}{"\n"}'
kubectl get secretstores -n my-namespace
kubectl get clustersecretstores
kubectl logs -n external-secrets deployment/external-secrets --tail=200 | grep my-app-config
kubectl events -n my-namespace --for externalsecret/my-app-config
```

The log is JSON, one line per error; the `error` field is the cause.

## Read the results

| `error` in the log | Meaning |
|---|---|
| `error processing spec.data[N] (key: <key>), err: Secret does not exist` | The store has no such key (or version, or property). Compare `remoteRef.key`, `version` and `property` with what the provider holds; the user checks the provider. |
| `could not get SecretStore "<name>", ... not found` (or `ClusterSecretStore`) | `secretStoreRef.name` or `kind` does not match a store. A SecretStore must be in the ExternalSecret's namespace; `kind` defaults to `SecretStore`. |
| `SecretStore "<name>" is not ready` | The store exists but its own `Ready` is `False`: see [stores.md](stores.md). |
| `using cluster store "<name>" is not allowed from namespace "<ns>": denied by spec.condition` | The ClusterSecretStore's `spec.conditions` (`namespaces`, `namespaceSelector`, `namespaceRegexes`) do not include this namespace. |
| A provider error (access denied, not found, throttled) | The store's credentials lack access to that key, or the provider refused. The user checks the provider's permissions. |

`dataFrom` (`extract`, `find`) errors appear the same way, with `spec.dataFrom[N]`.

## Proposed fix

- A wrong key, version or store name: fix it in the ExternalSecret's source; to test,
  patch the live object (ask first, see the main skill).
- A namespace not allowed by a ClusterSecretStore: the store's owners widen
  `spec.conditions`, or the app uses a store meant for its namespace. Widening a shared
  store changes who can read its secrets: a proposed fix for the owners.
- Provider permissions: the user grants the store's identity access to the key, in the
  provider.
- After a fix, ESO retries by itself; to sync at once, use the force-sync annotation
  (ask first, see the main skill).

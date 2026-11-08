# SecretStores and ClusterSecretStores

ESO validates each store against its provider and reports `Ready`. A store that is not
Ready makes every ExternalSecret using it fail.

## Investigate

```bash
kubectl get secretstores -A
kubectl get clustersecretstores
kubectl describe secretstore my-app-store -n my-namespace
kubectl get secretstore my-app-store -n my-namespace -o jsonpath='{.status.conditions}{"\n"}{.status.capabilities}{"\n"}'
kubectl get secretstore my-app-store -n my-namespace -o jsonpath='{.spec.provider}{"\n"}'
kubectl events -n my-namespace --for secretstore/my-app-store
kubectl logs -n external-secrets deployment/external-secrets --tail=200 | grep my-app-store
```

`spec.provider` names the provider and the references to its credentials (Secret
names and keys, a service account, workload identity settings). Read the names only;
never the Secrets.

## Read the results

| `Ready` | Reason, message | Meaning |
|---|---|---|
| `True` | `Valid`, `store validated` | The store works. |
| `True` | `ValidationUnknown`, `could not determine validation status` | The provider cannot be validated up front; problems show up on the first sync. |
| `False` | `InvalidProviderConfig`, `unable to create client` | ESO could not build a client: a referenced credentials Secret or key is missing, a service account cannot be used, a URL is wrong. |
| `False` | `InvalidProviderConfig`, `unable to validate store` | The client was built, but the provider refused (wrong credentials, no network to it, no permission). |
| `False` | `ProviderNotFound` | The provider in `spec.provider` is not compiled into this ESO version. |

- **Credentials in another namespace**: a SecretStore may only reference Secrets in its
  own namespace; a ClusterSecretStore names the namespace of each credential Secret.
- **Workload identity** (cloud identity for the service account): the service
  account's annotations and the cloud side's trust must match; the error text from the
  provider says which.
- **`StoreUnmaintained` events**: the provider is flagged as unmaintained in this ESO
  release; plan to move off it.

## Proposed fix

Credentials, identities and network paths to the provider are for the user: give them
the condition, the log line and the names of the referenced Secrets or service account.
Changing a shared ClusterSecretStore is for its owners.

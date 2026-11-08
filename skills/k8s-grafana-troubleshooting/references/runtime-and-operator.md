# Database, volume, plugins, login and the grafana-operator

## Investigate

```bash
kubectl get deployment my-grafana -n monitoring -o jsonpath='{.spec.replicas}{"\n"}{.spec.template.spec.securityContext}{"\n"}{.spec.template.spec.containers[0].image}{"\n"}'
kubectl get pvc -n monitoring
kubectl logs -n monitoring deployment/my-grafana -c grafana --tail=300 | grep -i -E "locked|permission denied|plugin|unauthorized|migration"
kubectl logs -n monitoring deployment/my-grafana -c grafana-sc-dashboard --tail=50 | grep -i -E "401|error"
kubectl get grafanas,grafanadashboards,grafanadatasources,grafanafolders -A
kubectl get grafanadashboard my-app -n monitoring -o jsonpath='{.spec.instanceSelector}{"\n"}{.status.conditions}{"\n"}'
kubectl get grafana my-grafana -n monitoring -o jsonpath='{.metadata.labels}{"\n"}{.status.stage}{" "}{.status.stageStatus}{" "}{.status.lastMessage}{"\n"}'
```

## Read the results

- **`Database locked, sleeping then retrying`, `database is locked`**: several Grafana
  replicas share one SQLite file on a volume. SQLite does not support that; more than
  one replica needs a shared MySQL or PostgreSQL database. The Grafana 13 migration to
  unified storage at start can also hit this on SQLite.
- **`permission denied` on `/var/lib/grafana`**: Grafana runs as user 472; the volume
  needs `fsGroup: 472` (or the chart's `initChownData`). The non-distroless images also
  print `GF_PATHS_DATA='...' is not writable`.
- **Plugins not installed**: the distroless image ignores `GF_INSTALL_PLUGINS`; use
  `GF_PLUGINS_PREINSTALL` or a custom image. Without internet access, plugin downloads
  fail. Angular plugins no longer load since Grafana 12.
- **Login fails, or the sidecar logs `401 Unauthorized`**: the admin password is stored
  in Grafana's database on first start. Changing the Secret afterwards does not change
  it, so the Secret and the database disagree. The user resets the password (for
  example with `grafana cli admin reset-admin-password` in the pod, or through the UI);
  never read the Secret.
- **Probes or scripts calling `grafana-server` or `grafana-cli`**: removed in Grafana
  13; the commands are `grafana server` and `grafana cli`.
- **grafana-operator: a condition `NoMatchingInstance`, reason `EmptyAPIReply`, "None
  of the available Grafana instances matched the selector, skipping reconciliation"**:
  the resource's `instanceSelector` does not match the `Grafana` resource's labels, the
  Grafana is in another namespace without `allowCrossNamespaceImport`, or the Grafana is
  not ready yet (`stage` not `complete` or `stageStatus` not `success`).
  `instanceSelector` is immutable: the resource must be recreated.
- **`DashboardSynchronized` or `DatasourceSynchronized` `False`, `ApplyFailed`**: the
  message lists the error per Grafana instance (invalid JSON, a datasource the dashboard
  needs).

## Proposed fix

Database, volume, replicas, image and plugins are settings of the Grafana installation:
proposed fixes for its owners, in the chart values or manifests. For the operator, fix
the labels or recreate the resource with the right `instanceSelector`, in its source:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl delete grafanadashboard my-app -n monitoring
kubectl apply -f my-app-grafanadashboard.yaml
# Undo: apply the old my-app-grafanadashboard.yaml again
```

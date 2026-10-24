# Provisioning: datasources and dashboards from files

Grafana reads provisioning files at start: datasources from
`/etc/grafana/provisioning/datasources/*.yaml`, dashboard providers from
`/etc/grafana/provisioning/dashboards/*.yaml`, and each provider's dashboard JSON files
from the folder it names. A broken **datasource** file stops Grafana; a broken
**dashboard** file only skips that dashboard.

## Investigate

```bash
kubectl get pods -n monitoring -l app=my-grafana
kubectl logs -n monitoring my-grafana-0 -c grafana --previous --tail=30
kubectl logs -n monitoring deployment/my-grafana -c grafana --tail=500 | grep logger=provisioning
kubectl get deployment my-grafana -n monitoring -o jsonpath='{range .spec.template.spec.containers[*].volumeMounts[*]}{.name}{" "}{.mountPath}{"\n"}{end}'
kubectl get configmap my-grafana-datasources -n monitoring -o yaml
kubectl get configmap my-grafana-dashboards -n monitoring -o yaml
```

With the Helm chart's sidecar, also:

```bash
kubectl get configmaps -A -l grafana_dashboard --show-labels
kubectl logs -n monitoring deployment/my-grafana -c grafana-sc-dashboard --tail=50
kubectl get deployment my-grafana -n monitoring -o jsonpath='{range .spec.template.spec.containers[*]}{.name}{" "}{.env}{"\n"}{end}'
```

The sidecar's environment shows `LABEL`, `LABEL_VALUE`, `NAMESPACE` (which namespaces
it watches) and `FOLDER`.

## Read the results

| Log line | Meaning |
|---|---|
| `Error: ✗ invalid service state: Failed ... Datasource provisioning error: datasource.yaml config is invalid. Only one datasource per organization can be marked as default` | Two datasources have `isDefault: true` (across all datasource files of the org). |
| `Datasource provisioning error: ...` with a YAML error | The datasource file does not parse. |
| `could not parse provisioning config file: <file> error: ...` | A dashboard provider file does not parse; Grafana stops. |
| `failed to load dashboard from ` `file=<path>` `error=<JSON error>` | That dashboard JSON is invalid; Grafana skips it and keeps running. |
| `the same UID is used more than once`, `dashboard title is not unique in folder` | Two dashboards collide; only one is shown. |
| Sidecar `ApiException when calling kubernetes: ... 403` | The sidecar's service account may not read ConfigMaps in the namespaces it watches. |

- **A dashboard ConfigMap the sidecar ignores**: its label key or value does not match
  the sidecar's `LABEL` and `LABEL_VALUE` (kube-prometheus-stack uses
  `grafana_dashboard: "1"`), or it is in a namespace outside the sidecar's `NAMESPACE`
  (by default only Grafana's own).
- **A change that does not show up**: datasource files are read only at start;
  dashboard files are re-read every `updateIntervalSeconds` (default 10). A ConfigMap
  update reaches a mounted volume after up to about a minute; a `subPath` mount never
  updates.

## Proposed fix

Fix the file in the source the ConfigMap comes from (chart values, a GitOps
repository): one `isDefault`, valid YAML or JSON, unique UIDs, the right sidecar label.
Then restart Grafana for datasource changes (ask first, see the main skill); dashboard
changes are picked up by themselves.

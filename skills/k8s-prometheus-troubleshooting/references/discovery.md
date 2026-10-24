# Discovery: ServiceMonitors and PodMonitors without targets

Three things must line up for a target to appear:

1. The **Prometheus** selects the monitor: `serviceMonitorSelector` matches its labels
   and `serviceMonitorNamespaceSelector` matches its namespace (`podMonitorSelector`
   and `podMonitorNamespaceSelector` for PodMonitors).
2. The **monitor** selects the Service (`spec.selector` against the Service's labels,
   `spec.namespaceSelector` for other namespaces) or, for a PodMonitor, the pods.
3. The monitor's **endpoint** names a port the Service (or pod) has: `endpoints[].port`
   is the port's `name`.

## Investigate

```bash
kubectl get prometheus my-prometheus -n monitoring -o jsonpath='{.spec.serviceMonitorSelector}{"\n"}{.spec.serviceMonitorNamespaceSelector}{"\n"}'
kubectl get servicemonitor my-app -n my-namespace -o jsonpath='{.metadata.labels}{"\n"}{.spec.selector}{"\n"}{.spec.namespaceSelector}{"\n"}{.spec.endpoints}{"\n"}'
kubectl get services -n my-namespace --show-labels
kubectl get service my-app -n my-namespace -o jsonpath='{range .spec.ports[*]}{.name}{" "}{.port}{" -> "}{.targetPort}{"\n"}{end}'
kubectl get namespace my-namespace --show-labels
kubectl get --raw '/api/v1/namespaces/monitoring/services/prometheus-operated:web/proxy/api/v1/scrape_pools'
kubectl get --raw '/api/v1/namespaces/monitoring/services/prometheus-operated:web/proxy/api/v1/targets?state=dropped' | jq -r '.data.droppedTargets[].discoveredLabels | [.__meta_kubernetes_namespace, .__meta_kubernetes_service_name, .__meta_kubernetes_endpoint_port_name, .__address__] | @tsv'
```

## Read the results

| What Prometheus shows | Where it breaks |
|---|---|
| No job `serviceMonitor/<ns>/<name>/<n>` | Step 1: the Prometheus does not select the monitor. Compare its labels with `serviceMonitorSelector` (kube-prometheus-stack selects `release: <helm release>` by default) and its namespace with `serviceMonitorNamespaceSelector`. |
| The job exists, no targets, nothing dropped | Step 2: `spec.selector` matches no Service, or the Service is in a namespace `spec.namespaceSelector` does not include (by default only the monitor's own namespace). |
| The job exists, the Service's endpoints are dropped | Step 3: `endpoints[].port` names no port of the Service. The dropped target's `__meta_kubernetes_endpoint_port_name` shows the names that exist. |
| The job exists, no targets, the Service has no endpoints | The Service selects no ready pods: `k8s-workload-troubleshooting` or `k8s-network-troubleshooting`. |

Selector semantics: an **empty** selector (`{}`) matches all; an **unset** (null)
`serviceMonitorSelector`, `podMonitorSelector` or `ruleSelector` matches nothing, and an
unset namespace selector matches only Prometheus' own namespace.

A numeric `port` is rejected when the ServiceMonitor is created
(`spec.endpoints.port in body must be of type string`); a Service port without a name
cannot be used by `port` at all (use `targetPort` with the container port, or name the
Service port).

If the operator runs with several Prometheus instances, a monitor can be selected by
one and not another; check the one the user looks at.

## Proposed fix

- Add the selected label to the monitor, or fix `endpoints[].port`, in the app's chart
  or manifests; to test, patch the live monitor (ask first, see the main skill).
- Name the Service port, in the app's source.
- Widening a Prometheus resource's selectors changes what it scrapes for everyone (and
  its load): a proposed fix for its owners.

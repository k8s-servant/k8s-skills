# metrics-server, KEDA and the VPA

## metrics-server

metrics-server scrapes each kubelet and serves `metrics.k8s.io` through the APIService
`v1beta1.metrics.k8s.io`. `kubectl top` and the HPA's CPU and memory metrics need it.

```bash
kubectl get apiservice v1beta1.metrics.k8s.io -o jsonpath='{.spec.service}{"\n"}{range .status.conditions[*]}{.type}={.status} {.reason}: {.message}{"\n"}{end}'
kubectl get deployment,pods -n kube-system -l k8s-app=metrics-server
kubectl logs -n kube-system deployment/metrics-server --tail=100
kubectl top nodes
```

- `error: Metrics API not available` from `kubectl top`: no `metrics.k8s.io` API is
  registered; metrics-server is not installed.
- APIService `Available False` with `MissingEndpoints`, `ServiceNotFound` or
  `FailedDiscoveryCheck`: metrics-server is not Ready or not reachable from the API
  server (a NetworkPolicy, a firewall on its port).
- metrics-server `0/1 Running` and logs `Failed to scrape node ... x509: cannot validate
  certificate for <ip> because it doesn't contain any IP SANs`, then `"Failed probe"
  probe="metric-storage-ready" err="no metrics to serve"`: it cannot verify the kubelets'
  serving certificates. The fix is kubelet certificates signed by the cluster CA;
  `--kubelet-insecure-tls` is only for test clusters.
- `dial tcp <ip>:10250: i/o timeout`: the network between metrics-server and the
  kubelets.

## KEDA

KEDA's operator (namespace `keda`) reconciles each ScaledObject into an HPA
`keda-hpa-<name>` (or `spec.advanced.horizontalPodAutoscalerConfig.name`), and
`keda-metrics-apiserver` serves the triggers as external metrics. An admission webhook
(`keda-admission`) checks new ScaledObjects; its `failurePolicy` is `Ignore`, so when it
is down, invalid objects are admitted.

```bash
kubectl get scaledobjects -n my-namespace
kubectl get hpa -n my-namespace -l scaledobject.keda.sh/name=my-app
kubectl get scaledobject my-app -n my-namespace -o jsonpath='{.status.externalMetricNames}{"\n"}{.status.hpaName}{"\n"}'
kubectl get triggerauthentications -n my-namespace
kubectl get deployments -n keda
kubectl get apiservice v1beta1.external.metrics.k8s.io -o jsonpath='{.spec.service}{"\n"}'
kubectl logs -n keda deployment/keda-operator --tail=200
kubectl logs -n keda deployment/keda-admission --tail=50
```

| Condition or event | Meaning |
|---|---|
| Ready `False` `ScaledObjectCheckFailed`: `ScaledObject doesn't have correct scaleTargetRef specification: ...`, event `Target resource doesn't exist` | The target is missing, misspelled or lacks `/scale`. No HPA is created. |
| Ready `False`: `failed to ensure HPA is correctly created for ScaledObject: ...`, event `KEDAScalerFailed` | A trigger's metadata does not parse (a cron schedule, a missing parameter) or its authentication cannot be resolved. |
| Active `False` `ScalerNotActive` | Triggers are below their activation threshold; with `minReplicaCount: 0` the workload stays at zero. |
| Fallback `True` `FallbackExists` | A scaler keeps failing and KEDA uses `fallback.replicas`. |
| Paused `True` | The annotation `autoscaling.keda.sh/paused: "true"` or `paused-replicas` is set. |
| `admission webhook "vscaledobject.kb.io" denied the request: the workload 'my-app' of type 'apps/v1.Deployment' is already managed by the hpa 'my-app'` | The workload already has an HPA; one autoscaler per workload. |

- Only one APIService can serve `external.metrics.k8s.io`. If its service is not
  `keda/keda-metrics-apiserver`, another adapter took it over and KEDA's metrics are not
  served.
- TriggerAuthentications: read only the printer columns (they show the names of Secrets
  and environment variables, not values). Never read the Secrets they name.
- KEDA 2.21 is tested with Kubernetes 1.34 to 1.36; check the compatibility table for
  newer clusters.

## VPA

```bash
kubectl get verticalpodautoscalers -n my-namespace
kubectl get verticalpodautoscaler my-app -n my-namespace -o jsonpath='{.spec.updatePolicy}{"\n"}{.status.conditions}{"\n"}{.status.recommendation}{"\n"}'
```

- Conditions `RecommendationProvided`, `LowConfidence`, `NoPodsMatched` (its target
  selects no pods), `FetchingHistory`, `ConfigUnsupported`.
- `updateMode: Off` only recommends; `Initial` applies at pod creation; `Recreate` and
  `InPlaceOrRecreate` change running pods. `Auto` is deprecated.
- Do not let a VPA and an HPA both act on CPU or memory of the same workload; an HPA on
  other metrics is fine.

## Proposed fix

Changes to metrics-server, KEDA, its APIService, ScaledObjects and VPAs change scaling
for others: proposed fixes for the user, in their source.

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl rollout restart deployment/keda-operator -n keda
# Undo: none needed; the restart only recreates the operator pod with the same template
```

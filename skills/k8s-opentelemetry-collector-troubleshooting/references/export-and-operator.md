# Export failures, processors, internal metrics and the operator

## Investigate

```bash
kubectl logs -n my-namespace deployment/my-collector --tail=500 | grep -E 'Exporting failed|Dropping data|Rejecting data|memory|Failed to watch|forbidden'
kubectl get configmap my-collector -n my-namespace -o jsonpath='{.data.config\.yaml}' | grep -E '^ *[a-z_]+(/[a-z0-9_-]+)?:$|^ *endpoint:'
kubectl get endpointslices -n my-namespace -l kubernetes.io/service-name=my-backend
kubectl logs -n my-namespace deployment/my-backend --tail=50
kubectl auth can-i list pods --as=system:serviceaccount:my-namespace:my-collector
```

Internal metrics (port 8888, only reachable from outside the pod when the config binds
them to `0.0.0.0`), through the API server's pod proxy if your credentials allow `get`
on `pods/proxy`:

```bash
kubectl get --raw /api/v1/namespaces/my-namespace/pods/my-collector-pod:8888/proxy/metrics | grep -E 'otelcol_(receiver_(accepted|refused)|exporter_(sent|send_failed|enqueue_failed|queue_size))'
```

## Read the results

**Exporters** (exporterhelper, 0.163):

| Log line | Meaning |
|---|---|
| `Exporting failed. Will retry the request after interval.` (info) with `error` and `interval` | A failed send, retried with backoff (5s to 30s, for 300s by default). |
| `Exporting failed. Dropping data.` with `no more retries left` and `dropped_items` | Retries ran out: data lost. |
| `Exporting failed. Rejecting data.` with `sending queue is full` | The queue (default 1000 batches) is full; new data is refused. |
| `Permanent error: ...` | Not retried (a 400-class answer from the backend). |

The `error` field names the network problem. For the gRPC exporter, `rpc error: code =
Unavailable desc = no children to pick from` means the endpoint's name resolved to no
address (a misspelled or missing Service); `connect: connection refused` means nothing
listens there (a wrong port, the backend down); `context deadline exceeded` points at a
firewall, a NetworkPolicy or a slow backend; TLS errors mean the exporter's `tls`
settings do not match the backend. Metrics:
`otelcol_exporter_send_failed_*`, `otelcol_exporter_enqueue_failed_*`,
`otelcol_exporter_queue_size` against `otelcol_exporter_queue_capacity` (counters have
no `_total` suffix).

**memory_limiter**: `Memory usage is above soft limit. Refusing data.` and senders get
`data refused due to high memory usage` (retryable); `otelcol_receiver_refused_*` rises.
Put `memory_limiter` first in each pipeline and `batch` after it; without it, a busy
collector is OOMKilled instead.

**k8s_attributes** needs `get`, `list` and `watch` on `pods` and `namespaces` (and
`replicasets` for deployment names, `nodes` for node names). Without them the client
logs `Failed to watch ... pods is forbidden: User "system:serviceaccount:..." cannot list
resource "pods" ...`; data flows on without the attributes, or stops with
`failed to wait for caches to sync` when `wait_for_metadata` is on.

**The OpenTelemetry Operator** (`opentelemetrycollectors` v1beta1, `instrumentations`):

- It creates `<name>-collector` (workload, Service, ServiceAccount) and renders the
  config into a ConfigMap `<name>-collector-<hash>`. Inline exporter headers are in clear
  text there; read only what you need.
- Status condition `Ready` with reason `Reconciled` or `ReconcileError` and the error as
  message; events `Error` on failure.
- Its default image is the core distribution, without `k8s_attributes` and most contrib
  components: set `spec.image` to `contrib` or `k8s`.
- It needs cert-manager for its webhook. If the operator is down, creating collectors
  fails with `failed calling webhook "mopentelemetrycollectorbeta.kb.io"`, but pods are
  created **without** injection (that webhook's `failurePolicy` is `Ignore`).
- Auto-instrumentation: the annotation `instrumentation.opentelemetry.io/inject-<lang>`
  goes on the pod template; the Instrumentation must exist before the pods start, so
  existing pods need a restart. The operator logs `no OpenTelemetry Instrumentation
  instances available`, `multiple OpenTelemetry Instrumentation instances available` or
  `support for <Lang> auto instrumentation is not enabled` (Go, PHP, Ruby and nginx are
  off by default), with the event `InstrumentationRequestRejected`.

```bash
kubectl logs -n opentelemetry-operator-system deployment/opentelemetry-operator-controller-manager -c manager --tail=100
kubectl get pods -n my-namespace -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.metadata.annotations}{" "}{range .spec.initContainers[*]}{.name}{" "}{end}{"\n"}{end}'
```

## Proposed fix

Exporter endpoints, TLS, queues, the memory_limiter, the collector's RBAC and the
operator's resources are shared settings: proposed fixes in their source, rolled out as
in the main skill. A backend that refuses data is fixed at the backend.

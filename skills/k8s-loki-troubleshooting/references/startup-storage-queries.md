# Start-up, readiness, storage, retention and queries

## Investigate

```bash
kubectl logs -n my-namespace deployment/my-loki --previous --tail=50
kubectl get pods -n my-namespace -l app=my-loki -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.containerStatuses[0].restartCount}{" "}{.status.containerStatuses[0].lastState.terminated.exitCode}{"\n"}{end}'
kubectl get --raw /api/v1/namespaces/my-namespace/services/my-loki:http-metrics/proxy/ready
kubectl get --raw /api/v1/namespaces/my-namespace/services/my-loki:http-metrics/proxy/services
kubectl get --raw /api/v1/namespaces/my-namespace/services/my-loki:http-metrics/proxy/ring
kubectl get --raw /api/v1/namespaces/my-namespace/services/my-loki:http-metrics/proxy/memberlist
kubectl get pvc -n my-namespace
```

## Read the results

**Start-up.** Loki validates its config, logs `msg="validating config" err="..."` and
exits 1 (several problems are listed under `MULTIPLE CONFIG ERRORS FOUND`). A YAML error
prints `failed parsing config: ...` instead. Schema errors are wrapped as `CONFIG ERROR:
invalid schema config: ...`:

| Message | Fix |
|---|---|
| `validating period_config: tsdb must always have periodic config for index set to 24h` | `index.period: 24h` for `store: tsdb` |
| `validating period_config: invalid schema version` | a known `schema` (`v13` for tsdb) |
| `must specify at least one schema configuration` | add `schema_config.configs` |
| `from time in schemas must be distinct and in increasing order` | order the periods by `from` |
| `schema v13 is required to store Structured Metadata and use native OTLP ingestion` | add a v13 period, or `allow_structured_metadata: false` |
| `compactor.delete-request-store should be configured when retention is enabled` | set `compactor.delete_request_store` |

**Readiness.** `/ready` answers `ready`, or 503 with `Some services are not Running:`,
`Ingester not ready: ...` or `waiting for 15s after being ready` (normal right after
start). `/services` lists each module's state; `Failed` names the broken part.

**Rings.** `empty ring`, `too many unhealthy instances in the ring`, `at least 2 live
replicas required, could only find 1`: ingesters are missing, not ACTIVE or fewer than
`replication_factor`. In microservices mode, `joining memberlist cluster failed` or
`failed to resolve members` points at the memberlist Service (port 7946) or a
NetworkPolicy between Loki pods.

**Storage.** `failed to flush chunks: <err>, num_chunks: ..., labels: ...` wraps the
object store's error (`NoSuchBucket`, `AccessDenied`, a timeout). On local disks, `no
space left on device`, or `Error writing to WAL, disk full`, means the volume is full
(the WAL stops at 90%). Retention only deletes with `compactor.retention_enabled: true`.

**Queries.**

| Status | Text | Limit |
|---|---|---|
| 400 | `the query time range exceeds the limit (query length: ..., limit: ...)` | `max_query_length` 721h |
| 400 | `this data is no longer available, it is past now - max_query_lookback (...)` | `max_query_lookback` |
| 400 | `the query would read too many bytes (query: ..., limit: ...)` | `max_query_bytes_read` |
| 400 | `maximum number of series (500) reached for a single query` | `max_query_series` |
| 429 | `too many outstanding requests` | queue per tenant |
| 504 | `request timed out, decrease the duration of the request or add more label matchers` | `query_timeout` 1m |

The Helm chart (now in grafana-community/helm-charts) defaults to `auth_enabled: true`,
so a Grafana datasource without a tenant gets `no org id`.

## Proposed fix

Schema, storage, retention, ring and query limits are Loki-wide settings: proposed fixes
for Loki's owners, in its source, rolled out as in the main skill. A full volume needs
the storage owners (`k8s-storage-troubleshooting`). Never call `/flush` or
`/ingester/shutdown` to "help" an ingester.

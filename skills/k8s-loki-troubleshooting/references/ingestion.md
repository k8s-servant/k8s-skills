# Ingestion: refused pushes, tenants and limits

The distributor checks each pushed line, then the tenant's ingestion rate; the ingester
checks per-stream limits and order. Loki logs a refused push (rate-limited, on by
default) as `level=error ... msg="write operation failed" details="<reason>"
org_id=<tenant>`, and counts refused lines in `loki_discarded_samples_total` by `reason`
and `tenant`.

## Investigate

```bash
kubectl logs -n my-namespace deployment/my-loki --tail=500 | grep 'write operation failed'
kubectl logs -n my-namespace deployment/my-app-logger --tail=20
kubectl get --raw /api/v1/namespaces/my-namespace/services/my-loki:http-metrics/proxy/metrics | grep loki_discarded_samples_total
kubectl get --raw "/api/v1/namespaces/my-namespace/services/my-loki:http-metrics/proxy/config?mode=diff"
kubectl get --raw /api/v1/namespaces/my-namespace/services/my-loki:http-metrics/proxy/config/tenant/v1/limits
```

## Read the results

| Status | Text (Loki 3.7) | `reason` | Limit and default |
|---|---|---|---|
| 400 | `entry for stream '...' has timestamp too old: <t>, oldest acceptable timestamp is: <t>` | `greater_than_max_sample_age` | `reject_old_samples` true, `reject_old_samples_max_age` 7d |
| 400 | `entry for stream '...' has timestamp too new: <t>` | `too_far_in_future` | `creation_grace_period` 10m (a client clock ahead) |
| 400 | `entry too far behind, entry timestamp is: <t>, oldest acceptable timestamp is: <t>` | `too_far_behind` | about 1h behind the newest line of the same stream |
| 400 | `entry out of order` | `out_of_order` | only with `unordered_writes: false` |
| 400 | `max entry size '<n>' bytes exceeded for stream '...' while adding an entry with length '<n>' bytes` | `line_too_long` | `max_line_size` 256KB |
| 400 | `entry for stream '...' has <n> label names; limit <n>` | `max_label_names_per_series` | 15 |
| 400 | `error at least one label pair is required per stream` | `missing_labels` | |
| 401 | `no org id` (not logged by Loki) | | `auth_enabled: true` and no `X-Scope-OrgID` header |
| 413 | `request body too large: <n> bytes, limit: <n> bytes` | `request_body_too_large` | |
| 429 | `ingestion rate limit exceeded for user <tenant> (limit: <n> bytes/sec) ...` | `rate_limited` | `ingestion_rate_mb` 4, `ingestion_burst_size_mb` 6 |
| 429 | `Per stream rate limit exceeded (limit: <n>/sec) while attempting to ingest for stream '...'` | `per_stream_rate_limit` | `per_stream_rate_limit` 3MB, burst 15MB |
| 429 | `maximum active stream limit exceeded when trying to create stream ...` | `stream_limit` | `max_global_streams_per_user` 5000 |

- The ingester groups refused lines of one stream as `entry with timestamp <t> ignored,
  reason: '<reason>'`, then `total ignored: <n> out of <n> for stream: ...`.
- **Tenants**: with `auth_enabled: false` every line goes to the tenant `fake`. With
  `true`, data pushed with one `X-Scope-OrgID` is invisible to queries with another; that
  shows as empty results, not an error.
- **Too many streams** comes from high-cardinality labels (a pod name, a request ID, a
  timestamp as a label); fix the client's labels before raising limits.
- A busybox `wget` client prints only the status line (`wget: server returned error:
  HTTP/1.1 400 Bad Request`); Loki's log has the reason.

## Proposed fix

- Client side (for its owners): correct timestamps or the clock, send `X-Scope-OrgID`,
  drop high-cardinality labels, split a hot stream with an extra label.
- Loki side (for Loki's owners, in its config or per-tenant overrides): raise
  `reject_old_samples_max_age`, `ingestion_rate_mb`, `per_stream_rate_limit` or
  `max_global_streams_per_user`, or set `auth_enabled` deliberately. These are proposed
  fixes, rolled out as in the main skill.

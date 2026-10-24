# Prometheus health: the resource, memory, disk and ingestion

## Investigate

```bash
kubectl get prometheus my-prometheus -n monitoring -o jsonpath='{.status.conditions}{"\n"}{.status.shardStatuses}{"\n"}'
kubectl get statefulsets,pods,pvc -n monitoring
kubectl describe pod prometheus-my-prometheus-0 -n monitoring
kubectl logs prometheus-my-prometheus-0 -n monitoring -c prometheus --tail=100
kubectl logs -n monitoring deployment/prometheus-operator --tail=100
kubectl get --raw '/api/v1/namespaces/monitoring/services/prometheus-operated:web/proxy/api/v1/status/tsdb' | jq '.data.headStats, .data.seriesCountByMetricName[:10]'
```

## Read the results

- **`Available` `False` or `Degraded`**, `Reconciled` `False`: the condition's message
  says what the operator could not do (an invalid field, a StatefulSet it could not
  update, pods not ready).
- **The pod `OOMKilled`**: Prometheus' memory grows with the number of active series
  (`headStats.numSeries`). `seriesCountByMetricName` and `labelValueCountByLabelName`
  in `/api/v1/status/tsdb` show what drives it, often a label with unbounded values
  (IDs, URLs). Reducing series works better than adding memory alone.
- **Out of disk**: the PVC is full; `retention` and `retentionSize` decide how much
  Prometheus keeps. See `k8s-storage-troubleshooting` for the volume.
- **Crash loop after a crash or a full disk**, with WAL or block errors in the log: the
  TSDB is damaged. The upstream advice is a backup and then removing the damaged block
  or WAL files: data loss, so a proposed fix for the owners, never run by you.
- **`out of order sample`, `out of bounds`, `too old sample`** in logs or metrics:
  samples with timestamps Prometheus cannot accept, usually from duplicate targets
  (two jobs scraping the same series) or clients pushing old data.

## Proposed fix

Memory, retention, storage size and shard count are fields of the Prometheus resource:
changes for the monitoring stack's owners, as proposed fixes. High-cardinality labels
are dropped at the source (the exporter) or with `metricRelabelings` on the monitor,
which you can propose with the evidence from `/api/v1/status/tsdb`.

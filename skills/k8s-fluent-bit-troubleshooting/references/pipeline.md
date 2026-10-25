# The pipeline: tail, kubernetes filter, outputs, retries and buffering

## Investigate

```bash
kubectl logs -n my-namespace daemonset/my-fluent-bit --tail=500 | grep -E 'inotify_fs_add|kubernetes|engine|net|output|paused'
kubectl get --raw /api/v1/namespaces/my-namespace/pods/my-fluent-bit-pod:2020/proxy/api/v1/metrics
kubectl get --raw /api/v1/namespaces/my-namespace/pods/my-fluent-bit-pod:2020/proxy/api/v2/metrics/prometheus
kubectl get --raw /api/v1/namespaces/my-namespace/pods/my-fluent-bit-pod:2020/proxy/api/v1/storage
kubectl auth can-i list pods --as=system:serviceaccount:my-namespace:my-fluent-bit
kubectl get clusterrole my-fluent-bit -o yaml
```

Read-only endpoints on port 2020: `/`, `/api/v1/uptime`, `/api/v1/metrics`,
`/api/v1/plugins`, `/api/v1/storage`, `/api/v1/health`, `/api/v2/metrics`,
`/api/v2/health`, and GET `/api/v2/reload`. None of them prints the config. Never request
`/api/v1/trace/...`: a GET there turns tracing on.

## Read the results

**Tail.** Each file it watches logs `[input:tail:tail.0] inotify_fs_add(): inode=...
name=...`. No such lines means the `Path` matches nothing; a wrong path logs no error.
`read_from_head` is off by default, so only lines written after start are read.
`Skip_Long_Lines` is off by default: a too-long line stops that file. On containerd and
CRI-O, lines look like `<time> stdout F <message>`; `multiline.parser docker, cri` parses
both formats. A classic `Parser docker` on CRI files keeps the raw line in `log` without
any warning.

**Kubernetes filter.** At start it logs `testing connectivity with API server...` and
`connectivity OK`. `could not get meta for POD ...` (or `for namespace`) means it could
not read the metadata: no `get`/`list`/`watch` on `pods` and `namespaces` for its
ServiceAccount, a wrong `Kube_URL`, or the API server unreachable. Records still flow,
without `kubernetes` fields. `incoming record tag (...) is shorter than kube_tag_prefix`
means `Tag` and `Kube_Tag_Prefix` do not fit (by default `kube.*` and
`kube.var.log.containers.`). A large pod spec needs a bigger `Buffer_Size`.

**Outputs and retries.**

| Log line | Meaning |
|---|---|
| `[net] getaddrinfo(host='h', err=4): Domain name not found` | `Host` does not resolve. |
| `[net] TCP connection failed: h:p (Connection refused)` | Nothing listens there. |
| `[net] connection #N timeout after N seconds to: h:p` | A firewall, NetworkPolicy or overloaded backend. |
| `[output:http:http.0] no upstream connections available to h:p` | The output could not connect (follows one of the above). |
| `[output:http:http.0] h:p, HTTP status=400` and a body | The backend refused the data; see its own logs. |
| `[engine] failed to flush chunk '...', retry in N seconds` | A failed send, retried. |
| `[engine] chunk '...' cannot be retried` | Retries are used up: those records are dropped. |
| `[engine] flush chunk '...' succeeded at retry N` | Recovered. |

`Retry_Limit` defaults to 1; `False` or `no_limits` retries forever. Metrics:
`fluentbit_output_retries_failed_total`, `fluentbit_output_dropped_records_total`,
`fluentbit_output_errors_total`, `fluentbit_input_records_total`.

**Backpressure.** `[input] tail.0 paused (mem buf overlimit - ...)` and later `resume
(mem buf overlimit ...)`: the input hit `Mem_Buf_Limit` because outputs are slow.
`storage.type filesystem` with `storage.path` buffers on disk instead; `paused (storage
buf overlimit ...)` is the same limit there.

**Health.** `/api/v2/health` turns unhealthy after `HC_Errors_Count` (5) errors or
`HC_Retry_Failure_Count` (5) failed retries within `HC_Period` (60s). The Helm chart's
readiness probe uses it, so a failing backend makes Fluent Bit pods not Ready.

## Proposed fix

Fix `Path`, the parser, `Host`/`Port`, `Retry_Limit` or buffering in the config's source,
and bind the filter's read role, as proposed fixes in the main skill. A backend that
refuses data is fixed at the backend.

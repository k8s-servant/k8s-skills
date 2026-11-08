# Targets that are down

A target is `down` when its last scrape failed; `lastError` says why, and the `up`
metric for it is `0`.

## Investigate

```bash
kubectl get --raw '/api/v1/namespaces/monitoring/services/prometheus-operated:web/proxy/api/v1/targets?state=active' | jq -r '.data.activeTargets[] | select(.health != "up") | [.labels.job, .scrapeUrl, .lastError, .lastScrapeDuration] | @tsv'
kubectl get servicemonitor my-app -n my-namespace -o jsonpath='{.spec.endpoints}{"\n"}'
kubectl get pods -n my-namespace -o wide
kubectl get networkpolicies -n my-namespace
```

`scrapeUrl` is the exact address, port and path Prometheus uses.

## Read the results

| `lastError` | Meaning |
|---|---|
| `server returned HTTP status 404 Not Found` | The app does not serve metrics at that path. Check `endpoints[].path` (default `/metrics`) against the app. |
| `server returned HTTP status 401 Unauthorized` / `403 Forbidden` | The endpoint needs authentication (`bearerTokenSecret`, `authorization`, TLS client certificates); the referenced credentials are Secrets for the user to check. |
| `... connect: connection refused` | Nothing listens on that port of the pod: wrong port, the app listens only on localhost, or it is not up yet. |
| `context deadline exceeded` | The scrape took longer than `scrapeTimeout`, or packets are dropped (a NetworkPolicy in the target's namespace, a firewall). |
| `body size limit exceeded` | The response is larger than `bodySizeLimit`. |
| `received unsupported Content-Type ...` or a content type error | Prometheus 3 checks the Content-Type strictly; the endpoint needs `fallbackScrapeProtocol` or a fixed exporter. |
| `x509: ...` | TLS to the target: wrong scheme (`https` versus `http`) or an untrusted certificate. |

## Proposed fix

- Wrong path, port or scheme: fix the endpoint in the monitor's source; to test, patch
  the live monitor (ask first, like the port example in the main skill).
- A NetworkPolicy blocking Prometheus: `k8s-network-troubleshooting`; the policy change
  is a proposed fix for its owners.
- Authentication: the user checks the referenced credentials.

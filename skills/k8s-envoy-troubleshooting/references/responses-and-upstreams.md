# Responses, flags and upstreams

Envoy writes no access log unless one is configured on the HTTP connection manager. The
default format has `%RESPONSE_FLAGS%` but not `%RESPONSE_CODE_DETAILS%`,
`%UPSTREAM_CLUSTER%` or `%UPSTREAM_TRANSPORT_FAILURE_REASON%`; if they are missing,
propose adding them (`log_format.text_format_source.inline_string` on the
`envoy.access_loggers.stdout` logger; plain `text_format` is deprecated in 1.40).

## Investigate

```bash
kubectl logs -n my-namespace deployment/my-envoy --tail=100 | grep -E ' (UH|UF|UO|NR|NC|UT|URX|UC|UR|LR|DC|RL|UAEX|DF) '
kubectl get --raw /api/v1/namespaces/my-namespace/services/my-envoy-admin:admin/proxy/clusters
kubectl get --raw "/api/v1/namespaces/my-namespace/services/my-envoy-admin:admin/proxy/stats?filter=(cluster.my-app.|http.ingress_http.|dns.)"
kubectl get --raw "/api/v1/namespaces/my-namespace/services/my-envoy-admin:admin/proxy/config_dump?resource=static_clusters"
kubectl get services,endpointslices -n my-namespace -o wide
```

## Read the results

| Flag | Status and body | Meaning |
|---|---|---|
| `UH` NoHealthyUpstream | 503 `no healthy upstream` | The cluster has no healthy host: none resolved, all failing health checks, or all ejected. |
| `UF` UpstreamConnectionFailure | 503 `upstream connect error or disconnect/reset before headers. reset reason: remote connection failure` (or `connection timeout`) | Connecting to the host failed. |
| `UO` UpstreamOverflow | 503, header `x-envoy-overloaded` | A circuit breaker (`max_connections`, `max_pending_requests`, `max_requests`, default 1024) refused it. |
| `NR` NoRouteFound | 404, empty body | No virtual host matches the Host header, or no route the path. |
| `NC` NoClusterFound | 503, empty body | The route names a cluster that does not exist (dynamic route tables). |
| `UT` UpstreamRequestTimeout | 504 `upstream request timeout` | No response within the route `timeout` (default 15s). |
| `URX` UpstreamRetryLimitExceeded | the last error | Retries used up. |
| `UC` UpstreamConnectionTermination | 503 `... reset reason: connection termination` | The backend closed the connection (often a keep-alive shorter than Envoy's idle timeout). |
| `DC` DownstreamConnectionTermination | | The client went away. |
| `DF` DnsResolutionFailed | | A DNS resolution failure (dynamic forward proxy). |

`%RESPONSE_CODE_DETAILS%` says the same in words: `no_healthy_upstream`,
`route_not_found`, `cluster_not_found`, `response_timeout`,
`upstream_reset_before_response_started{remote_connection_failure|delayed_connect_error:_Connection_refused}`.
Since 1.39 the transport reason (`delayed connect error: Connection refused`, TLS
validation errors) is only in `%UPSTREAM_TRANSPORT_FAILURE_REASON%`, not in the body.

**`/clusters`**: per host, `<cluster>::<ip:port>::cx_connect_fail::N`, `rq_error`,
`rq_timeout`, `health_flags::healthy` (or `/failed_active_hc`, `/failed_outlier_check`,
`/failed_eds_health`). A cluster with no hosts prints only its cluster-wide lines
(`max_connections`, `added_via_api`).

**DNS clusters**: `STRICT_DNS` turns every address a name resolves to into a host; with
a headless Service that is each pod, with a ClusterIP Service one host (kube-proxy
spreads behind it). A name that does not exist is a successful lookup with no addresses:
`update_success` rises, not `update_failure`; `membership_total` is 0; `dns.cares.not_found`
rises. Names are re-resolved every 5s (`dns_refresh_rate`).

**Stats**: `cluster.<name>.upstream_cx_connect_fail`, `upstream_cx_connect_timeout`,
`upstream_cx_none_healthy`, `upstream_rq_timeout`, `upstream_rq_pending_overflow`,
`upstream_rq_5xx`, `membership_healthy`, `membership_total`; `http.<stat_prefix>.no_route`,
`no_cluster`, `downstream_rq_5xx`; `listener.<address>.no_filter_chain_match`.

**Health and panic**: active health checks and outlier detection mark hosts unhealthy.
Below 50% healthy hosts (the panic threshold) Envoy sends to all hosts anyway, so a
failing cluster can give `UF` or 5xx instead of `UH`.

## Proposed fix

Correct the cluster address or port, the route's `domains` or `match`, timeouts or
circuit breakers in the bootstrap's source, as a proposed fix in the main skill. A
backend without endpoints is fixed at the backend (`k8s-network-troubleshooting`).

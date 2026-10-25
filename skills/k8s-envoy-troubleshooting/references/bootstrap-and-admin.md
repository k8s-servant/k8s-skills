# Bootstrap errors, the admin interface and images

## Bootstrap errors

Envoy reads its bootstrap (`-c /etc/envoy/envoy.yaml` in the official image) once, at
start. An invalid one is logged at `critical` and Envoy exits 1, so the pod goes to
`Error` and CrashLoopBackOff; read it with `kubectl logs --previous`. Match on the inner
message; the prefix has changed between versions.

```bash
kubectl logs -n my-namespace deployment/my-envoy --previous --tail=20
kubectl get pods -n my-namespace -l app=my-envoy -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.containerStatuses[0].restartCount}{" "}{.status.containerStatuses[0].lastState.terminated.exitCode}{"\n"}{end}'
kubectl get configmap my-envoy -n my-namespace -o yaml
```

| Message (1.40) | Meaning |
|---|---|
| `Protobuf message (type envoy.config.bootstrap.v3.Bootstrap reason INVALID_ARGUMENT: invalid JSON in ... @ <path>: ... no such field: '<name>') has unknown fields` | A misspelled or misplaced field; `@ <path>` says where. |
| `Unable to parse JSON as proto (...)` | A wrong type (a string where a number belongs, a duration without a unit). |
| `... Proto constraint validation failed (...)` | A value out of range (for example a zero `connect_timeout`). |
| `route: unknown cluster '<name>'` | A static route names an undefined cluster (static routes are checked at start). |
| `cluster manager: duplicate cluster '<name>'` | Two clusters with one name. |
| `Using deprecated option '<field>' ...` (warning), or an error with `If continued use of this field is absolutely necessary` | A field removed or about to be. |

Envoy can check a config without serving with `--mode validate`; running it is for the
user (it is not a read-only kubectl command).

## The admin interface

The admin listener (often port 9901) serves read-only GET endpoints: `/clusters`,
`/listeners`, `/stats` (`?filter=`, `?format=json|prometheus`), `/stats/prometheus`,
`/server_info`, `/ready`, `/runtime`, `/config_dump` with `?resource=`. Endpoints that
change state (`/quitquitquit`, `/healthcheck/fail`, `/healthcheck/ok`, `/logging`,
`/drain_listeners`, `/reset_counters`, `/runtime_modify`, profilers) need POST; a GET
there gets `405 Method GET not allowed, POST required.` and changes nothing. A path
listed in `admin.allow_paths` filtering answers 403 when blocked.

- `config_dump` tries to redact TLS private keys and passwords, but only in typed
  fields. Use only `?resource=static_clusters`, `dynamic_active_clusters`,
  `static_listeners`, `dynamic_listeners`, `static_route_configs` or
  `dynamic_route_configs`. Never the full dump, `*_secrets` or `/certs`.
- Reaching it: through the API server's service or pod proxy when admin listens on a pod
  address (`get` on `services/proxy` or `pods/proxy` is needed); from another pod with
  `wget` under "Ask first"; not at all when admin listens on `127.0.0.1` (Istio, Envoy
  Gateway, Contour's `127.0.0.1:9001`, Emissary's `localhost:8001`). The admin interface
  can shut Envoy down; exposing it is a decision for the user.

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl exec -n my-namespace deployment/my-web -- wget -q -O - http://my-envoy-admin.my-namespace:9901/clusters
```

## Images

`envoyproxy/envoy:<version>` is Ubuntu with only the Envoy binary (`sh`, `cat`, no curl
or wget); `distroless-<version>` has no shell; `debug-<version>` means debug symbols,
not tools. Read the admin interface from outside the Envoy container.

## Proposed fix

Fix the bootstrap in its source and restart Envoy, as in the main skill. If admin must be
reachable for troubleshooting, bind it to the pod address only behind a NetworkPolicy,
or keep it on `127.0.0.1` and use a port-forward; that choice is the user's.

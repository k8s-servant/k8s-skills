# Failing liveness, readiness and startup probes

The kubelet runs three kinds of probes, each with one of four mechanisms (`exec`,
`httpGet`, `tcpSocket`, `grpc`):

- **Readiness probe** failing: the container is marked not ready, the pod's `Ready`
  condition is `False`, and the pod gets no traffic from Services. The container is
  **not** restarted. Readiness probes run for the container's whole life.
- **Liveness probe** failing: after `failureThreshold` failures in a row the kubelet
  kills the container, and it is restarted according to the restart policy.
- **Startup probe**: while it is configured and has not yet succeeded, liveness and
  readiness probes do not run. If it never succeeds, the container is killed and
  restarted.

Fields and defaults: `initialDelaySeconds` 0, `periodSeconds` 10, `timeoutSeconds` 1,
`successThreshold` 1 (must be 1 for liveness and startup), `failureThreshold` 3. An HTTP
probe succeeds for status codes from 200 up to 399; an `exec` probe succeeds on exit
code 0. `httpGet.path` defaults to `/`.

## Investigate

```bash
kubectl get pods -n my-namespace -l app=my-app
kubectl describe pod my-pod -n my-namespace
kubectl events -n my-namespace --for pod/my-pod
kubectl get deployment my-app -n my-namespace -o jsonpath='{.spec.template.spec.containers[*].readinessProbe}'
kubectl get deployment my-app -n my-namespace -o jsonpath='{.spec.template.spec.containers[*].livenessProbe}'
kubectl get deployment my-app -n my-namespace -o jsonpath='{.spec.template.spec.containers[*].ports}'
kubectl logs my-pod -n my-namespace --tail=100
kubectl get endpointslices -n my-namespace -l kubernetes.io/service-name=my-app -o yaml
kubectl describe service my-app -n my-namespace
```

`describe` prints each probe on one line, for example
`Readiness: http-get http://:80/healthz delay=0s timeout=1s period=5s #success=1 #failure=3`.

## Read the results

The `Unhealthy` event message says how the probe failed:

- **`HTTP probe failed with statuscode: 404`**: the path does not exist in the app.
  Compare the probe's `path` with what the app serves (its docs or logs).
- **`statuscode: 500` or `503`**: the endpoint exists but the app reports itself
  unhealthy, often because a dependency is down. The app's logs say which.
- **`connection refused`**: nothing listens on that port, yet. A few of these right after
  start are normal while the app starts. If they never stop, the probe `port` does not
  match the port the app listens on (compare with the container's `ports` and the logs).
- **`context deadline exceeded`, `Client.Timeout exceeded`**: the app answers slower than
  `timeoutSeconds` (default 1 second). Under load, or right after start, that may be the
  real behaviour of the app.
- **Liveness failures right after each start, then a restart**: the app needs longer to
  start than `initialDelaySeconds` plus `failureThreshold` × `periodSeconds`. A startup
  probe is the documented answer for slow starts.

A pod that is `Running`, `0/1` ready, with zero restarts and readiness `Unhealthy`
events, is a readiness problem, not a Service problem: a not-ready pod is never a ready
endpoint. The Service's EndpointSlice still lists the pod's address, with the condition
`ready: false`; the `ENDPOINTS` column of `kubectl get endpointslices` shows that address
anyway, so read the conditions. If the pods are Ready and traffic still does not arrive,
continue with `k8s-network-troubleshooting`.

## Proposed fix

Point the probe at a path and port the app serves, raise `timeoutSeconds` or
`failureThreshold` when the app is slow but healthy, or add a startup probe for slow
starts. Removing a probe hides the problem; propose it only as a last resort and say so.

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl patch deployment my-app -n my-namespace --type=json -p '[{"op": "replace", "path": "/spec/template/spec/containers/0/readinessProbe/httpGet/path", "value": "/ready"}]'
# Undo: kubectl patch deployment my-app -n my-namespace --type=json -p '[{"op": "replace", "path": "/spec/template/spec/containers/0/readinessProbe/httpGet/path", "value": "/healthz"}]'
```

The JSON patch path uses the container's index (`containers/0` is the first container);
check the index in the pod spec first.

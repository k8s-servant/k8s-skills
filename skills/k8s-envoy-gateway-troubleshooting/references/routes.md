# Routes: attachment, backends and ReferenceGrants

A route attaches to a Gateway listener when its `parentRefs` name the Gateway (and
optionally `sectionName` for one listener), its `hostnames` intersect the listener's
`hostname`, and the listener's `allowedRoutes` admits its namespace and kind. Each
`backendRefs` entry must name an existing Service (or another supported kind) that the
route may reference.

## Investigate

```bash
kubectl get httproute my-app -n my-namespace -o jsonpath='{.spec.parentRefs}{"\n"}{.spec.hostnames}{"\n"}{range .spec.rules[*]}{.matches}{" -> "}{.backendRefs}{"\n"}{end}'
kubectl get httproute my-app -n my-namespace -o jsonpath='{range .status.parents[*].conditions[*]}{.type}={.status} {.reason}: {.message}{"\n"}{end}'
kubectl get gateway my-gateway -n my-namespace -o jsonpath='{range .spec.listeners[*]}{.name}{" "}{.hostname}{" "}{.allowedRoutes}{"\n"}{end}'
kubectl get services -A | grep my-app
kubectl get referencegrants -A -o yaml
kubectl logs -n my-namespace deployment/my-client --tail=10
```

## Read the results

| Condition, reason | Client sees | Meaning |
|---|---|---|
| Accepted `False`, `NoMatchingListenerHostname` | 404 | `hostnames` and the listener's `hostname` do not intersect. |
| Accepted `False`, `NotAllowedByListeners` | 404 | `allowedRoutes.namespaces` (default `Same`) or `kinds` excludes the route. |
| Accepted `False`, `NoMatchingParent` | 404 | `parentRefs` names no listener (wrong `sectionName` or `port`). |
| No status for this Gateway at all | 404 | `parentRefs` names another Gateway or namespace, or the GatewayClass is not Envoy Gateway's. |
| ResolvedRefs `False`, `BackendNotFound` | 500 | The backend Service (name, namespace, port) does not exist. |
| ResolvedRefs `False`, `RefNotPermitted` | 500 | The backend is in another namespace and no ReferenceGrant there allows `HTTPRoute` from this namespace to `Service`. |
| ResolvedRefs `False`, `InvalidKind` | 500 | `backendRefs` names a kind Envoy Gateway does not support there. |
| BackendsAvailable `False`, `EndpointsNotFound` | 503 | The Service exists but has no ready endpoints. |

A 404 also comes from requests whose Host header or path matches no rule of an attached
route. A ReferenceGrant lives in the **target** namespace and lists `from` (group, kind,
namespace of the route) and `to` (kind, optionally name).

## Proposed fix

- Fix the route's `hostnames`, `parentRefs` or `backendRefs` in its source; to test,
  patch the live route (ask first, see the main skill).
- A cross-namespace backend: the owners of the target namespace add a ReferenceGrant, as
  a proposed fix (it opens their Services to another namespace's routes):

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl apply -f my-other-namespace-referencegrant.yaml
# Undo: kubectl delete -f my-other-namespace-referencegrant.yaml
```

with a ReferenceGrant in the backend's namespace, `from` `gateway.networking.k8s.io`
`HTTPRoute` in the route's namespace, `to` `""` `Service` (optionally with the
Service's name).

# Ingress and Gateway API not routing

An Ingress or a Gateway API route only describes routing; a controller (ingress
controller, or Gateway implementation) does the work. With no controller for the class,
nothing happens. The Ingress API is frozen; new setups usually use Gateway API.

kind runs neither by default, so this page is checked against the docs only.

## Investigate

```bash
kubectl get ingress -n my-namespace
kubectl describe ingress my-app -n my-namespace
kubectl get ingressclass
kubectl get gatewayclass
kubectl get gateway -A
kubectl describe gateway my-gateway -n my-namespace
kubectl get httproute -n my-namespace
kubectl describe httproute my-app -n my-namespace
kubectl get referencegrant -A
```

Then check the backend Service as in [services.md](services.md).

## Read the results

Ingress:

- **No `ADDRESS`** on the Ingress: no controller has taken it. Check `ingressClassName`
  against `kubectl get ingressclass`; without a class, the default class (annotation
  `ingressclass.kubernetes.io/is-default-class: "true"`) is used, if there is one.
- **Backend errors in `describe ingress`**: the backend `service.name` and
  `service.port` must name an existing Service and one of its ports (number or name).
- **A `404` from the controller**: no rule matched the host or path; check `host`,
  `path` and `pathType`.

Gateway API (route status is reported per parent Gateway; for the listeners, the
GatewayClass, ListenerSets and the CRDs, continue with `k8s-gateway-api-troubleshooting`):

- **`Accepted: False`** on the HTTPRoute, reasons:
  - `NotAllowedByListeners`: the listener's `allowedRoutes` does not allow the route's
    namespace. The default is `Same`, the Gateway's own namespace.
  - `NoMatchingListenerHostname`: the route's hostnames match no listener.
  - `NoMatchingParent`: the `parentRefs` name no existing Gateway or listener.
- **`ResolvedRefs: False`**, reasons:
  - `BackendNotFound`: the backend Service does not exist.
  - `RefNotPermitted`: a backend in another namespace needs a ReferenceGrant in that
    namespace.
  - `InvalidKind`, `UnsupportedProtocol`: the reference is of a kind or protocol the
    implementation does not support.
- **The Gateway has no address or `Programmed: False`**: the implementation did not set
  it up; its controller's logs say why.

## Proposed fix

Correct a backend port on an Ingress (path index and values as you found them):

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl patch ingress my-app -n my-namespace --type=json -p '[{"op": "replace", "path": "/spec/rules/0/http/paths/0/backend/service/port/number", "value": 80}]'
# Undo: kubectl patch ingress my-app -n my-namespace --type=json -p '[{"op": "replace", "path": "/spec/rules/0/http/paths/0/backend/service/port/number", "value": 8080}]'
```

Creating a ReferenceGrant, changing a Gateway listener's `allowedRoutes`, or installing
a controller changes who can route where: propose it to the owner of the Gateway or the
target namespace, as a proposed fix with the object to create and its delete as undo.

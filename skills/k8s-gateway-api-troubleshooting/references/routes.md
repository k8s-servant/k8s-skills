# Routes that do not attach or do not resolve

A route attaches to each Gateway (or listener) in its `parentRefs`, and the Gateway's
controller writes one entry per parent under `status.parents`. `Accepted` says whether
it attached; `ResolvedRefs` says whether its `backendRefs` are usable. The two are
independent: a route can be Accepted with broken backends, or resolved but attached to
nothing.

## Investigate

```bash
kubectl get httproute my-app -n my-namespace -o jsonpath='{range .status.parents[*]}{.parentRef}{"\n"}{range .conditions[*]}{"  "}{.type}={.status} {.reason}: {.message}{"\n"}{end}{end}'
kubectl get httproute my-app -n my-namespace -o yaml
kubectl get gateway my-gateway -n my-namespace -o jsonpath='{range .spec.listeners[*]}{.name}{" "}{.protocol}{" "}{.port}{" "}{.hostname}{" allowedRoutes="}{.allowedRoutes}{"\n"}{end}'
kubectl get namespace my-namespace --show-labels
kubectl get referencegrants -n my-other-namespace -o yaml
kubectl get grpcroutes,tlsroutes -A
kubectl get backendtlspolicies -A
```

## Read the results

**Attaching (`Accepted`).** A parent ref names a Gateway by `name`, and by `namespace`
when the Gateway is elsewhere (the default is the route's own namespace). `sectionName`
picks one listener by name, `port` one by port; without them the route tries every
listener of the Gateway.

- `NoMatchingParent`: `sectionName` or `port` names no listener. Compare them with the
  Gateway's listener names and ports.
- `NotAllowedByListeners`: a listener exists, but its `allowedRoutes` refuses the route.
  `allowedRoutes.namespaces.from` is `Same` by default (the API server fills it in: the
  Gateway's namespace only),
  `All`, or `Selector` (namespaces whose labels match `selector`; check the route
  namespace's labels). `allowedRoutes.kinds` limits the route kinds; by default a
  listener takes the kinds that fit its protocol.
- `NoMatchingListenerHostname`: the route's `hostnames` share no name with the
  listener's `hostname`. A listener without a hostname matches every host; a wildcard
  `*.example.com` matches `my-app.example.com` and deeper names, but not
  `example.com`.
- No `status.parents` at all: no controller owns any of the parents. Check that the
  Gateway named exists in the namespace the route implies, and that its class is
  Accepted.
- `PartiallyInvalid` `True`: some rules are invalid. Its message starts with `Dropped
  Rule` (the controller serves the valid rules) or `Fall Back` (it keeps serving the
  last version of the route that was valid).

Attaching to a Gateway in another namespace is controlled by the listener's
`allowedRoutes`, not by a ReferenceGrant.

**Resolving (`ResolvedRefs`).**

- `BackendNotFound`: the backend Service (or other kind) does not exist in the namespace
  the reference names. Implementations answer that rule with an error (Envoy Gateway
  with 500) rather than dropping it.
- `RefNotPermitted`: the backend is in another namespace, and no ReferenceGrant in that
  namespace allows it. A grant lists `from` (group `gateway.networking.k8s.io`, the
  route's kind, the route's namespace) and `to` (group `""`, kind `Service`, and
  optionally the name). A grant in the route's namespace has no effect.
- `InvalidKind`: the reference names a group or kind the implementation does not
  support as a backend.
- `UnsupportedProtocol`: the Service port's `appProtocol` is one the implementation
  cannot speak for this route.
- A backend `port` must be one of the Service's `port` values (not the `targetPort`).

**Route kinds.** When an HTTPRoute and a GRPCRoute on one listener share a hostname,
the implementation accepts only one of them: the older one (then the first by
`namespace/name`); the other gets `Accepted` `False`. TLSRoute passes TLS through by SNI
and needs a listener with protocol `TLS`; TCPRoute and UDPRoute need `TCP` and `UDP`
listeners. In Gateway API 1.6 TLSRoute, TCPRoute and UDPRoute are `v1` in the Standard
channel; their `v1alpha2` versions are served only by the experimental CRDs, so old
manifests fail with `no matches for kind` on a standard install.

**BackendTLSPolicy.** It targets a Service (`targetRefs`) and sets `validation.hostname`
and either `caCertificateRefs` (ConfigMaps with a CA bundle) or
`wellKnownCACertificates`. Its status lists each Gateway under `ancestors`, with
`Accepted` and `ResolvedRefs`; `ResolvedRefs` `False` with `InvalidCACertificateRef`,
`InvalidKind` or `NoValidCACertificate` means the CA bundle reference does not resolve.

## Proposed fix

Correcting a route's own `parentRefs`, `hostnames` or `backendRefs` is reversible:
ask-first, with the values you found as the undo (the main skill has an example).
Creating a ReferenceGrant gives one namespace's routes access to another namespace's
Services, and changing `allowedRoutes` gives namespaces access to a shared Gateway: both
are decisions for the owners of the target namespace or the Gateway.

Allow routes from one namespace to reach one Service in another:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl apply -f - <<'YAML'
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: my-app-routes
  namespace: my-other-namespace
spec:
  from:
    - group: gateway.networking.k8s.io
      kind: HTTPRoute
      namespace: my-namespace
  to:
    - group: ""
      kind: Service
      name: my-api
YAML
# Undo: kubectl delete referencegrant my-app-routes -n my-other-namespace
```

# GatewayClasses, Gateways, listeners and CRDs

A GatewayClass is claimed by the controller whose name equals its `controllerName`. That
controller then reconciles every Gateway of the class: it sets the Gateway's `Accepted`
and `Programmed`, gives it addresses, and writes a status entry per listener. Nothing
happens to a Gateway whose class no controller claims.

## Investigate

```bash
kubectl get gatewayclasses -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.controllerName}{" "}{.status.conditions}{"\n"}{end}'
kubectl describe gateway my-gateway -n my-namespace
kubectl get gateway my-gateway -n my-namespace -o jsonpath='{.status.addresses}{"\n"}{.spec.allowedListeners}{"\n"}'
kubectl get listenersets -A
kubectl get listenerset my-listeners -n my-namespace -o jsonpath='{.spec.parentRef}{"\n"}{range .status.conditions[*]}{.type}={.status} {.reason}: {.message}{"\n"}{end}{range .status.listeners[*]}{.name}{"\n"}{range .conditions[*]}{"  "}{.type}={.status} {.reason}: {.message}{"\n"}{end}{end}'
kubectl get events -n my-namespace --field-selector involvedObject.name=my-gateway
kubectl get crds -o jsonpath='{range .items[?(@.spec.group=="gateway.networking.k8s.io")]}{.metadata.name}{" "}{.metadata.annotations.gateway\.networking\.k8s\.io/bundle-version}{" "}{.metadata.annotations.gateway\.networking\.k8s\.io/channel}{"\n"}{end}'
kubectl get validatingadmissionpolicy safe-upgrades.gateway.networking.k8s.io -o yaml
```

## Read the results

**The class.**

- `Accepted` `Unknown`, `Pending` (`Waiting for controller`): no controller claims the
  `controllerName`. Compare it, character by character, with a class that is Accepted
  and with the implementation's documentation, and check that the implementation runs.
  `controllerName` is immutable: the API server refuses a change with `Value is
  immutable`, so the fix is a new class (or recreating this one) and pointing the
  Gateways at it.
- `Accepted` `False`, `InvalidParameters`: `parametersRef` names a missing or malformed
  object, or sets a namespace on a cluster-scoped kind (or leaves it out on a namespaced
  one).
- `SupportedVersion` `False`, `UnsupportedVersion` (experimental): the controller does
  not support the Gateway API version of the installed CRDs. It may still accept the
  class on a best-effort basis, or refuse it with `Accepted` `False`.

**The Gateway.**

- `Accepted` and `Programmed` `Unknown`, `Pending`: no controller has reconciled it;
  see the class.
- `Accepted` `False`, `ListenersNotValid`: no listener is valid. With some valid
  listeners the Gateway stays `Accepted` and `Programmed`, and only the bad listeners
  fail: check every listener, not just the Gateway.
- `Accepted` `False`, `UnsupportedAddress` or `InvalidParameters`: a requested address
  of an unsupported type, or a bad `infrastructure.parametersRef`.
- `Programmed` `False`, `AddressNotAssigned` (`No addresses have been assigned to the
  Gateway`) or `AddressNotUsable`: no address yet (for example a LoadBalancer Service
  still pending, or no valid listener), or a requested static address that cannot be
  used.

**Listeners.** Each has `Accepted`, `Programmed`, `ResolvedRefs` and `Conflicted`, and
an `attachedRoutes` count.

- `ResolvedRefs` `False`, `InvalidCertificateRef`: a TLS `certificateRefs` entry names
  a Secret that does not exist or is not a valid TLS Secret. Envoy Gateway says `No
  valid secrets exist: certificate refs 0: Secret my-namespace/my-app-tls does not
  exist.`. `RefNotPermitted`: the certificate is in another namespace without a
  ReferenceGrant there. Never read the Secret to check it; the condition is enough.
- `ResolvedRefs` `False`, `InvalidRouteKinds`: `allowedRoutes.kinds` names a kind the
  implementation does not support for the protocol (Envoy Gateway: `TCPRoute is not
  supported, kind must be one of [HTTPRoute GRPCRoute]` on an HTTP listener).
- `Conflicted` `True`, `ProtocolConflict` (`All listeners for a given port must use a
  compatible protocol`) or `HostnameConflict`: listeners on one port disagree. The API
  server already refuses two listeners with the same port, protocol and hostname
  (`Combination of port, protocol and hostname must be unique for each listener`).
- `Accepted` `False`, `PortUnavailable`, `UnsupportedProtocol` or `UnsupportedValue`:
  the port or protocol cannot be served by this implementation.
- `Programmed` `False`, `Invalid` (`Listener is invalid, see other Conditions for
  details.`): read the listener's other conditions.

**ListenerSets** (Standard in 1.6). A Gateway admits them only through
`spec.allowedListeners`, which allows none by default. `Accepted` `False`,
`NotAllowed`: the Gateway's `allowedListeners` does not admit the ListenerSet's
namespace. `ParentNotAccepted`: the Gateway itself is not Accepted. Each listener entry
has the same conditions as a Gateway listener, plus `ListenerConflict` and
`TooManyListeners`.

**CRDs and channels.** Each Gateway API CRD carries the annotations
`gateway.networking.k8s.io/bundle-version` (for example `v1.6.1`) and
`gateway.networking.k8s.io/channel` (`standard` or `experimental`). All CRDs should
come from one release and one channel. Implementations often bundle their own copy (Envoy
Gateway 1.9.2 installs v1.6.1, experimental). The install files of 1.5 and later add the
ValidatingAdmissionPolicy `safe-upgrades.gateway.networking.k8s.io`, which refuses
experimental CRDs over standard ones (`Installing experimental CRDs on top of standard
channel CRDs is prohibited by default.`) and CRDs older than v1.5.0. A kind or version
missing from `kubectl api-resources` means the CRD, or that version of it, is not
installed or not served; `k8s-api-troubleshooting` covers `no matches for kind`.

## Proposed fix

Changes to GatewayClasses, Gateways, listeners, ListenerSets and the Gateway API CRDs
affect every team that uses the Gateway, and CRD changes affect the whole cluster: hand
them to their owners as proposed fixes, never run them. Name the object and the field,
and give the undo with the values you found.

Replace a class whose `controllerName` is wrong (the field is immutable), then point the
Gateways at it:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl apply -f - <<'YAML'
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: my-working-class
spec:
  controllerName: example.com/my-gateway-controller
YAML
kubectl patch gateway my-gateway -n my-namespace --type=merge -p '{"spec": {"gatewayClassName": "my-working-class"}}'
# Undo: kubectl patch gateway my-gateway -n my-namespace --type=merge -p '{"spec": {"gatewayClassName": "my-class"}}'
# Undo: kubectl delete gatewayclass my-working-class
```

Let a Gateway accept ListenerSets from its own namespace:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl patch gateway my-gateway -n my-namespace --type=merge -p '{"spec": {"allowedListeners": {"namespaces": {"from": "Same"}}}}'
# Undo: kubectl patch gateway my-gateway -n my-namespace --type=json -p '[{"op": "remove", "path": "/spec/allowedListeners"}]'
```

# GatewayClasses, Gateways, the proxy and policies

## Investigate

```bash
kubectl get gatewayclass -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.controllerName}{" "}{.status.conditions}{"\n"}{end}'
kubectl get gateway my-gateway -n my-namespace -o yaml
kubectl get deployments,pods,services -n envoy-gateway-system
kubectl logs -n envoy-gateway-system deployment/envoy-gateway --tail=100
kubectl get envoyproxies -A -o yaml
kubectl get backendtrafficpolicies,clienttrafficpolicies,securitypolicies,envoypatchpolicies -A
kubectl get backendtrafficpolicy my-policy -n my-namespace -o jsonpath='{.spec.targetRefs}{"\n"}{.status}{"\n"}'
```

## Read the results

- **GatewayClass `Accepted` `False`, `InvalidParameters`**: its `parametersRef` (an
  EnvoyProxy) is missing or invalid. A GatewayClass with another `controllerName`
  belongs to another implementation; Envoy Gateway ignores its Gateways.
- **Gateway `Programmed` `False`, `AddressNotAssigned`** (`No addresses have been
  assigned to the Gateway`): the Envoy Service is a LoadBalancer without an address.
  On clusters without load balancers, an EnvoyProxy with
  `spec.provider.kubernetes.envoyService.type` `NodePort` or `ClusterIP`, referenced by
  the Gateway's `spec.infrastructure.parametersRef` or the GatewayClass, avoids that.
- **Listener conditions**: `ResolvedRefs` `False` `InvalidCertificateRef` (the TLS
  Secret is missing or invalid; do not read it, check its name and whether
  cert-manager issued it), `Conflicted` (two listeners with the same port and
  hostname), `UnsupportedProtocol`.
- **No proxy pods for the Gateway**: Envoy Gateway's log says why it could not create
  them (an invalid EnvoyProxy, RBAC, resources).
- **A policy without effect**: its `targetRefs` name no existing Gateway or route
  (then it has no status at all), or its status shows `Accepted` `False` with
  `Invalid`, `Conflicted` (another policy of the same kind targets the same object) or
  `Overridden` (a more specific policy, on the route, wins over one on the Gateway).
  EnvoyPatchPolicy reports `Programmed`.
- **Gateway API version**: Envoy Gateway 1.9 installs the Gateway API 1.6 CRDs
  (experimental channel); older CRDs left by another tool can make routes or kinds
  disappear silently.

## Proposed fix

Gateways, listeners, GatewayClasses, EnvoyProxy and policies are shared: their owners
change them in the source, as proposed fixes. A stuck Envoy Gateway controller or proxy
is for the installation's owners; restarting the controller does not interrupt traffic
already flowing through the proxies:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl rollout restart deployment/envoy-gateway -n envoy-gateway-system
# Undo: kubectl rollout undo deployment/envoy-gateway -n envoy-gateway-system
```

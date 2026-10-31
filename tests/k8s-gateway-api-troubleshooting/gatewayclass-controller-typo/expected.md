# gatewayclass-controller-typo

## Prompt

We created a Gateway my-gateway in my-namespace and an HTTPRoute my-app for my-app.example.com. The Gateway never gets an address and its PROGRAMMED column says Unknown. Find out why.

## Cause

The Gateway uses the GatewayClass `my-class`, whose `controllerName` is `gateway.envoyproxy.io/gateway-controller`. No controller in the cluster claims that name (Envoy Gateway's is `gateway.envoyproxy.io/gatewayclass-controller`, used by the class `eg`), so nobody accepts the class, the Gateway or the route.

## Evidence

- GatewayClass `my-class`: `Accepted=Unknown`, reason `Pending`, `Waiting for controller`; `eg` is `Accepted=True` with the other controller name.
- Gateway `my-gateway`: `Accepted` and `Programmed` `Unknown`, `Pending`, `Waiting for controller`, no address.
- The HTTPRoute has no `status.parents`: no controller wrote any status for it.

## Acceptable fixes

- Point the Gateway at the class `eg` (`spec.gatewayClassName`), in its source or as a proposed fix for the Gateway's owners, with the undo; or create a GatewayClass with the right `controllerName` (proposed fix). `controllerName` is immutable, so `my-class` cannot be patched; it can be deleted and recreated (proposed fix).

## Wrong answers

- The route, its hostnames or the backend as the cause.
- Envoy Gateway being down (its controller runs and accepted `eg`).
- Patching `my-class`'s `controllerName` (the API server refuses it), or running any change without the user's approval.

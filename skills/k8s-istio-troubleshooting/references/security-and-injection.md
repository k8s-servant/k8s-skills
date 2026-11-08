# Security, injection, istiod and ambient

The server's sidecar enforces PeerAuthentication (does it accept plaintext?) and
AuthorizationPolicies (is this caller allowed?). Sidecars are added by istiod's
injection webhook when a pod is created.

## Investigate

```bash
kubectl get peerauthentications,authorizationpolicies -A
kubectl get authorizationpolicy -n my-namespace -o yaml
kubectl get pods -n my-namespace -o jsonpath='{range .items[*]}{.metadata.name}{" sa="}{.spec.serviceAccountName}{" "}{.spec.containers[*].name}{"\n"}{end}'
kubectl logs -n my-namespace deployment/my-app -c istio-proxy --tail=30
kubectl get namespaces -L istio-injection -L istio.io/rev -L istio.io/dataplane-mode
kubectl get mutatingwebhookconfigurations | grep -i istio
kubectl get pods -n istio-system
kubectl logs -n istio-system deployment/istiod --tail=100
kubectl events -n my-namespace
```

## Read the results

- **403 `rbac_access_denied_matched_policy[none]`**: an ALLOW policy selects the
  server, and no rule matched. Compare the caller's identity
  (`cluster.local/ns/<namespace>/sa/<service account>`, from its pod's service account)
  with the rule's `principals` or `namespaces`, and the request's path and method with
  `to`. `[ns[...]-policy[...]-rule[...]]` names a DENY policy that matched.
- **Identities need mTLS**: `principals` and `namespaces` in a rule only match callers
  with a sidecar (or ztunnel); a plaintext caller has no identity and never matches.
- **`Connection reset by peer` at the client, `NR filter_chain_not_found` at the
  server**: the server's PeerAuthentication (namespace-wide, mesh-wide in
  `istio-system`, or per workload) is `STRICT`, and the client sends plaintext, usually
  because it has no sidecar (namespace not labelled, `sidecar.istio.io/inject: "false"`,
  or pods created before the label).
- **No `istio-proxy` container**: the namespace lacks `istio-injection=enabled` or the
  matching `istio.io/rev`, the pod opts out, or the injection webhook failed at creation
  (events: `failed calling webhook "namespace.sidecar-injector.istio.io"`).
- **Proxies without configuration** (sidecars not ready, `istio-proxy` logs about
  connecting to `istiod`): istiod is down or unreachable.
- **Ambient mode** (`istio.io/dataplane-mode=ambient` on the namespace): there are no
  sidecars; L4 and mTLS happen in the `ztunnel` pod on each node (its logs show each
  connection), and L7 policies need a waypoint proxy (`istio.io/use-waypoint`).

## Proposed fix

- AuthorizationPolicy and PeerAuthentication changes decide who may talk to whom: the
  user changes them in the source, with the narrowest rule (add the caller's principal,
  or use `PERMISSIVE` only while clients move into the mesh).
- A client that should be in the mesh: label its namespace in the source, then restart
  the workload (ask first, see the main skill).
- istiod problems are for the mesh's administrators.

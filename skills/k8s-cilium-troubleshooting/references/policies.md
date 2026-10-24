# Policies: drops, default deny, DNS and L7

Cilium enforces Kubernetes NetworkPolicies, CiliumNetworkPolicies (CNP) and
CiliumClusterwideNetworkPolicies (CCNP) together. Policies only allow; a connection
needs the client's egress and the server's ingress to be allowed. An endpoint that no
policy selects in a direction is open in that direction.

## Investigate

```bash
kubectl get ciliumnetworkpolicies,networkpolicies -A
kubectl get ciliumclusterwidenetworkpolicies
kubectl get ciliumnetworkpolicy my-policy -n my-namespace -o yaml
kubectl get pods -n my-namespace --show-labels
kubectl get ciliumendpoints -n my-namespace -o wide
kubectl logs -n my-namespace deployment/my-web --tail=20
```

The flows themselves, from the agent on the client's or server's node (ask first, as in
the main skill):

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl exec cilium-xxxxx -n kube-system -c cilium-agent -- hubble observe --last 100 --namespace my-namespace --verdict DROPPED
kubectl exec cilium-xxxxx -n kube-system -c cilium-agent -- hubble observe --last 50 --namespace my-namespace --protocol dns
kubectl exec cilium-xxxxx -n kube-system -c cilium-agent -- cilium-dbg endpoint list
kubectl exec cilium-xxxxx -n kube-system -c cilium-agent -- cilium-dbg policy get
```

`cilium-dbg policy get` prints every policy the agent has loaded, as it understands
them.

## Read the results

| Symptom | Hubble | Meaning |
|---|---|---|
| Client time-out | `Policy denied DROPPED`, `policy-verdict:none INGRESS DENIED` | The server is selected for ingress and no rule allows this client (labels, namespace, port). |
| Client time-out | `... EGRESS DENIED` | The client is selected for egress and no rule allows this destination. |
| `bad address`, DNS time-out | DNS packets to kube-dns `DROPPED` | An egress policy on the client does not allow DNS. |
| HTTP 403, body `Access denied` | `http-request DROPPED` (L7) | An L7 HTTP rule allows the port but not that method, path or host. |
| A toFQDNs destination unreachable | no DNS seen by the proxy | toFQDNs needs a DNS rule (`rules.dns`) toward kube-dns so Cilium learns the names' addresses. |
| Allowed although a policy should drop | `AUDITED` | Policy audit mode is on (`policy-audit-mode` in `cilium-config`): drops are only logged. |

- **Selectors**: `endpointSelector` and `fromEndpoints`/`toEndpoints` match pod labels;
  a peer in another namespace needs `k8s:io.kubernetes.pod.namespace: <ns>` in the
  selector, otherwise only the policy's own namespace matches.
- **Default deny** applies per direction as soon as any rule with that direction
  (`ingress` or `egress` section) selects the endpoint. `enableDefaultDeny` on a policy
  can turn that off for it (not for L7 rules).
- **DNS for egress policies**: allow `toEndpoints` with
  `k8s:io.kubernetes.pod.namespace: kube-system` and `k8s-app: kube-dns`, on port 53
  UDP and TCP; add `rules.dns` with a `matchPattern` for DNS visibility and toFQDNs.
- **Since 1.19** a `**.` wildcard in toFQDNs matches several subdomain levels; since
  1.20 empty CNPs are rejected.

## Proposed fix

Write the narrowest additional rule that allows the failing traffic (a new rule in the
same policy or a second policy; rules add up), in the policy's source. The user applies
it; never change policies yourself. Show the drop you saw and the rule that would allow
it.

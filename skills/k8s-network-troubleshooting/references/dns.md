# DNS: names that do not resolve

Every Service gets a name `my-app.my-namespace.svc.cluster.local` (the cluster domain
may differ). A pod's `/etc/resolv.conf` has a search list that starts with its own
namespace, and `ndots:5`, so a short name such as `my-app` is tried in the client's own
namespace first.

## Investigate

```bash
kubectl get service my-app -n my-namespace
kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=100
kubectl get service kube-dns -n kube-system
kubectl get endpointslices -n kube-system -l kubernetes.io/service-name=kube-dns
kubectl get configmap coredns -n kube-system -o yaml
kubectl get pod my-pod -n my-other-namespace -o jsonpath='{.spec.dnsPolicy}{"\n"}{.spec.dnsConfig}{"\n"}'
```

From inside the client, if its image has the tools (asked first, as in SKILL.md):

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl exec my-pod -n my-other-namespace -- cat /etc/resolv.conf
kubectl exec my-pod -n my-other-namespace -- nslookup kubernetes.default
kubectl exec my-pod -n my-other-namespace -- nslookup my-app.my-namespace
```

## Read the results

- **`kubernetes.default` resolves, `my-app` does not**: the name is wrong for where the
  client runs. From another namespace the client needs `my-app.my-namespace`. Check the
  Service exists in that namespace with that exact name.
- **Nothing resolves**: CoreDNS is down, has no ready endpoints, or the client cannot
  reach it. Check the CoreDNS pods and their logs; an egress NetworkPolicy on the client
  that does not allow DNS also does this ([networkpolicy.md](networkpolicy.md)).
- **`dnsPolicy: Default`** makes the pod use the node's resolver, not cluster DNS, so
  Service names do not resolve. `ClusterFirst` is the usual value.
- **External names fail, cluster names work**: CoreDNS's upstream (`forward` in the
  `Corefile`) or the node's resolver is the problem; the CoreDNS logs show the errors.
  Continue with `k8s-coredns-troubleshooting` for CoreDNS itself: its Corefile, upstreams,
  stub domains, rewrites and NodeLocal DNSCache.
- **A headless Service** (`clusterIP: None`) resolves to the pod addresses directly; no
  Ready pod means no records.

## Proposed fix

Use the full name in the client's configuration, in its source. Changing the CoreDNS
configuration affects every pod in the cluster, so a cluster administrator reviews and
applies it:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl -n kube-system edit configmap coredns
# Undo: kubectl -n kube-system edit configmap coredns, and restore the Corefile you saved before editing
```

Save the current `Corefile` (from the `get configmap coredns` output above) before
proposing a change, so the undo has it.

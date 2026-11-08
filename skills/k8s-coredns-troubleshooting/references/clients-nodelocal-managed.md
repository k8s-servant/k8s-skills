# Clients, NodeLocal DNSCache, scaling and managed clusters

## Clients that load CoreDNS

A pod with the usual `dnsPolicy: ClusterFirst` gets `nameserver <kube-dns IP>` (or
`169.254.20.10` with NodeLocal DNSCache), a search list that starts with its own
namespace, and `options ndots:5`. A name with fewer than five dots is first tried with
every search suffix, so `example.com` costs several NXDOMAIN lookups, for A and AAAA,
before the real one.

```bash
kubectl get pod my-client -n my-namespace -o jsonpath='{.spec.dnsPolicy}{" "}{.spec.dnsConfig}{"\n"}'
kubectl top pods -n kube-system -l k8s-app=kube-dns
```

- **Lookups that are usually fast but sometimes take exactly about 5 seconds**: a
  conntrack race drops one of the A and AAAA queries a glibc client sends together, and
  the resolver waits for its 5 s timeout. Client fixes: `dnsConfig.options:
  [{name: single-request-reopen}]` (glibc only; musl, as in Alpine, ignores it), or
  NodeLocal DNSCache, which skips the conntrack path.
- **Heavy load from a few clients**: a trailing dot (`example.com.`) or a lower `ndots`
  (`dnsConfig.options: [{name: ndots, value: "2"}]`) in the client's spec avoids the
  search-list lookups.
- `dnsPolicy: Default` uses the node's resolver, not CoreDNS; `ClusterFirstWithHostNet`
  is needed for `hostNetwork` pods to use CoreDNS.

## NodeLocal DNSCache

A DaemonSet `node-local-dns` in kube-system (label `k8s-app=node-local-dns`, host
network) runs a CoreDNS cache on each node at `169.254.20.10`, and forwards cluster
names to CoreDNS through the Service `kube-dns-upstream`, and other names to the node's
resolver. Its Corefile is in the ConfigMap `node-local-dns`.

```bash
kubectl get daemonset node-local-dns -n kube-system
kubectl get pods -n kube-system -l k8s-app=node-local-dns -o wide
kubectl logs -n kube-system -l k8s-app=node-local-dns --tail=50 --prefix
kubectl get configmap node-local-dns -n kube-system -o yaml
kubectl get service kube-dns-upstream -n kube-system
```

- **Only pods on one node fail**: that node's `node-local-dns` pod is down or restarting.
  An OOMKilled node-cache does not clean up its packet rules, so DNS on that node stops
  briefly each time it fails.
- **`Unable to lookup IP address of Upstream service kube-dns-upstream`**: the
  `kube-dns-upstream` Service is missing.
- **`Error checking/adding iptables rule`** or **`Failed to add non-existent interface`**:
  it cannot set up its local address on that node.
- **A stub domain added to CoreDNS has no effect**: node-cache sends names outside the
  cluster to the node's resolver, not to CoreDNS; the stub domain must also be in the
  `node-local-dns` Corefile.

## Scaling

CoreDNS needs about `(pods + services) / 1000 + 54` MB with the default settings, and
kubeadm limits it to 170Mi; `pods verified` uses much more. A `kube-dns-autoscaler` (or
`dns-autoscaler`) Deployment sets the replica count from the cluster's size and undoes a
manual scale-up or scale-down.

```bash
kubectl get pods -n kube-system -l k8s-app=kube-dns -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.containerStatuses[0].lastState.terminated.reason}{"\n"}{end}'
kubectl get deployment -n kube-system | grep -i autoscaler
kubectl get configmap -n kube-system | grep -i autoscaler
```

`OOMKilled` in the last state, liveness-probe restarts, `REFUSED` answers or `Local
health request ... took more than 1s` warnings mean CoreDNS is short of memory or
replicas: propose a higher memory limit or more replicas in the Deployment's source (or
the autoscaler's ConfigMap), as a proposed fix with the current values for the undo.

## Managed clusters

- **AKS** (more in `k8s-aks-troubleshooting`): the `coredns` ConfigMap is managed and reset by AKS. Custom configuration goes
  in the ConfigMap `coredns-custom` in kube-system: keys ending in `.server` add server
  blocks, keys ending in `.override` add lines to the default block. CoreDNS needs a
  restart to read it.
- **EKS**: the CoreDNS add-on overwrites direct edits of the Corefile at its next update;
  a custom Corefile goes in the add-on's `configurationValues` (`corefile` key) and must
  keep the `ready` plugin, which the readiness probe uses.
- **GKE**: Standard clusters run kube-dns (a CoreDNS-based implementation since 1.36),
  configured through the `kube-dns` ConfigMap (`stubDomains`, `upstreamNameservers`);
  there is no Corefile to edit. Autopilot uses Cloud DNS. Look for a `kube-dns`
  Deployment, not `coredns`.

```bash
kubectl get configmap coredns-custom -n kube-system -o yaml
kubectl get configmap kube-dns -n kube-system -o yaml
kubectl get deployment -n kube-system -l k8s-app=kube-dns
```

Changes in these ConfigMaps or the add-on's settings serve the whole cluster: hand them
to the user as proposed fixes, with the current content saved for the undo.

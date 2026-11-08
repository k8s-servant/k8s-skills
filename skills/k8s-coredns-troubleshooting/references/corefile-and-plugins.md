# The Corefile and its plugins

kubeadm's default Corefile (Kubernetes 1.37, CoreDNS 1.14.6) has one server block:

```text
.:53 {
    errors
    health {
       lameduck 5s
    }
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa {
       pods insecure
       fallthrough in-addr.arpa ip6.arpa
       ttl 30
    }
    prometheus :9153
    forward . /etc/resolv.conf {
       max_concurrent 1000
    }
    cache 30 {
       disable success cluster.local
       disable denial cluster.local
    }
    loop
    reload
    loadbalance
}
```

Plugins run in an order fixed when CoreDNS is built, not in the order written:
`rewrite` always runs before `kubernetes`, and `hosts` before `forward`. A query goes to
the server block with the most specific matching zone; a block for `example.com:53`
needs its own `errors` line, or its failures are not logged.

## Investigate

```bash
kubectl get configmap coredns -n kube-system -o jsonpath='{.data.Corefile}'
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=100 --prefix
kubectl logs -n kube-system -l k8s-app=kube-dns --prefix | grep -E 'Running configuration|Reloading|reload failed|Restart failed'
kubectl logs -n kube-system my-coredns-pod --previous --tail=20
kubectl get pods -n kube-system -l k8s-app=kube-dns -o jsonpath='{range .items[*]}{.metadata.name}{" ready="}{.status.containerStatuses[0].ready}{" restarts="}{.status.containerStatuses[0].restartCount}{" last="}{.status.containerStatuses[0].lastState.terminated.reason}{"\n"}{end}'
kubectl get replicasets -n kube-system -l k8s-app=kube-dns
kubectl get configmap kubelet-config -n kube-system -o yaml
```

The last command exists on kubeadm clusters and shows the kubelet's `clusterDNS`,
`clusterDomain` and `resolvConf`. Each pod logs `plugin/reload: Running configuration
SHA512 = <hash>` when it starts or reloads: pods with different hashes serve different
Corefiles.

Metrics, if your credentials allow `get` on `pods/proxy` in kube-system (the `view` role
does not; if it is refused, skip this):

```bash
kubectl get --raw /api/v1/namespaces/kube-system/pods/my-coredns-pod:9153/proxy/metrics | grep -E '^coredns_(dns_responses_total|proxy_healthcheck_failures_total|forward_max_concurrent_rejects_total|reload_failed_total|panics_total)'
```

## Read the results

Start-up and reload:

- **`/etc/coredns/Corefile:<line> - Error during parsing: Unknown directive '<word>'`**:
  a misspelled plugin, or one this build does not include. **`Wrong argument count or
  unexpected line ending after '<token>'`** or **`Syntax error: Unexpected token`**: a
  missing argument or brace on that line. **`cannot serve dns://example.com.:53 - it is
  already defined`**: the same zone appears in two server blocks. A process that cannot
  start exits, so the pod restarts into CrashLoopBackOff.
- **`[ERROR] Restart failed: ...`** then **`[ERROR] plugin/reload: Corefile changed but
  reload failed: ...`** in running pods: the edited Corefile is invalid, and the pod
  keeps serving the configuration it had. It does not retry the same broken file; it
  reloads when the ConfigMap changes again. **`[WARNING] plugin/reload: Corefile parse
  failed`** is the same for a syntax error.
- **A rollout that is stuck with one old pod Running and new pods crashing**: the
  Deployment's `maxUnavailable: 1` keeps one old pod, which still answers from the old
  configuration. Losing that pod (a node drain, an eviction) stops cluster DNS.
- **Edits that seem ignored**: the kubelet can take up to about a minute to update the
  mounted ConfigMap, and `reload` checks every 30 seconds or so; allow two minutes.
  Without the `reload` plugin, only a restart reads the change.
- **`[FATAL] plugin/loop: Loop (127.0.0.1:<port> -> :53) detected for zone ".", see
  https://coredns.io/plugins/loop#troubleshooting. Query: "HINFO ..."`**: queries come
  back to CoreDNS. Usually `forward . /etc/resolv.conf` on nodes whose resolv.conf lists
  `127.0.0.53` (systemd-resolved): the kubelet's `resolvConf` should point at the real
  one, `/run/systemd/resolve/resolv.conf`. Also `forward` to a loopback address or to the
  `kube-dns` ClusterIP.

Upstreams (`forward`):

- **`[ERROR] plugin/errors: 2 <name> A: read udp <pod ip>:<port>-><upstream>:53: i/o
  timeout`**: the upstream does not answer. **`connect: connection refused`**: nothing
  listens there. **`network is unreachable`** or **`no route to host`**: no path to it.
  Compare the address with the `forward` line and the node's resolver. Health-check
  failures are not logged; they only show in `coredns_proxy_healthcheck_failures_total`.
- **`no healthy proxies`**: every upstream in `forward` is marked down.
- **`5 <name> A: concurrent queries exceeded maximum 1000`**: `REFUSED` because
  `max_concurrent` was reached; the upstream is slow, or there is too much load
  (`coredns_forward_max_concurrent_rejects_total`).
- SERVFAIL answers are cached for 5 seconds, so a fixed upstream can take a moment to
  show.

The `kubernetes` plugin:

- **`[INFO] plugin/kubernetes: waiting for Kubernetes API before starting server`**,
  **`[WARNING] plugin/kubernetes: starting server with unsynced Kubernetes API`** and
  **`[INFO] plugin/ready: Plugins not ready: "kubernetes"`**: CoreDNS has no list of
  Services yet; it answers SERVFAIL for cluster names until it has, and the pod is not
  Ready. **`Failed to watch: failed to list *v1.EndpointSlice: ... is forbidden: User
  "system:serviceaccount:kube-system:coredns" cannot list ...`**: its ClusterRole
  `system:coredns` is missing or changed (`k8s-rbac-troubleshooting`).
- **A name under `cluster.local` that is not a Service gets NXDOMAIN** from CoreDNS
  itself: the plugin only falls through for the reverse zones.
- **`pods disabled`** (the plugin's default when the line is missing) answers NXDOMAIN
  for `<a-b-c-d>.<namespace>.pod.cluster.local` names; kubeadm sets `pods insecure`.
- **The zone on the `kubernetes` line differs from the kubelet's `clusterDomain`**: the
  pods' search list names a domain CoreDNS does not serve, so short names fail.

Answers changed on purpose:

- **`rewrite name <from> <to>`**: CoreDNS looks up `<to>` instead. A `<to>` that does not
  exist makes `<from>` NXDOMAIN, and nothing is logged. An exact rule (two names) gives
  the answer back under the name that was asked; `suffix`, `prefix`, `substring` and
  `regex` rules need `answer auto` (or `answer name`) for that, or some clients reject
  the answer. **`plugin/rewrite: invalid arguments for <name> rule`** at reload means
  options after a two-name rule: `answer auto` needs a match type first (`rewrite name
  suffix ...`).
- **`hosts`** answers only the names it lists; without `fallthrough`, every other name in
  that server block is NXDOMAIN.
- **A stub domain** (`example.com:53 { forward . <ip> }`): that zone goes only to that
  address. Compare it with the DNS server it should reach (often a Service's ClusterIP
  that changed when the Service was recreated).

To see answers in the log, the `log` plugin must be added to the Corefile: that logs
every query in the cluster, so it is a proposed fix, removed again afterwards.

## Proposed fix

Change the Corefile in its source (the ConfigMap's manifest, the Helm values, or the
managed cluster's own ConfigMap, see
[clients-nodelocal-managed.md](clients-nodelocal-managed.md)), keeping everything else as
it is, and apply it as in SKILL.md, with the saved Corefile for the undo. Examples of
the changed lines:

- A typo: `loadbalance` instead of `loadbalanse`.
- An upstream: `forward . 10.0.0.53` with the resolver that the network team names, or
  back to `forward . /etc/resolv.conf`.
- A loop: fix the kubelet's `resolvConf` on the nodes (a node configuration change, for
  the cluster's operators); pointing `forward` at a real resolver only fixes CoreDNS,
  not pods with `dnsPolicy: Default`.
- A rewrite: the target as the Service's full name, `my-app.my-namespace.svc.cluster.local`.

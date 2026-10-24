# Node NotReady or Unknown

Tell the two states apart first, from the `Ready` condition in `kubectl describe node`:

- **`Unknown`**, message "Kubelet stopped posting node status": the node controller has
  not heard from the kubelet within `node-monitor-grace-period` (50 seconds by default).
  The kubelet is stopped or crashed, the machine is down, or it cannot reach the API
  server. Every other condition is `Unknown` too.
- **`False`**: the kubelet is running and says the node is not healthy. The reason and
  message name the part that is not ready, often the container runtime or the network
  plugin ("container runtime network not ready", "cni plugin not initialized").

## Investigate

```bash
kubectl get nodes -o wide
kubectl describe node my-node
kubectl get lease my-node -n kube-node-lease -o jsonpath='{.spec.renewTime}'
kubectl get events -A --field-selector involvedObject.kind=Node,involvedObject.name=my-node
kubectl get pods -A -o wide --field-selector spec.nodeName=my-node
```

Compare the Lease's `renewTime` with the current time (if Leases are forbidden to you,
use the conditions' `LastHeartbeatTime` in `describe node`). The kubelet renews it every 10
seconds by default, so a renew time minutes old means the kubelet is not reaching the
API server. If several nodes went `NotReady` at the same time, suspect what they share
(the network, the API server, a node pool upgrade) rather than each node.

## Read the results

- **Taints**: an `Unknown` node gets `node.kubernetes.io/unreachable` with `NoSchedule`
  and `NoExecute`; a `False` node gets `node.kubernetes.io/not-ready`. New pods are not
  scheduled there.
- **Pods on the node**: they tolerate those `NoExecute` taints for 300 seconds by
  default, then they are evicted and their controllers create replacements elsewhere.
  Until the node comes back or is removed, the old pods may show `Terminating` or
  `Unknown`. DaemonSet pods are not evicted.
- **StatefulSet pods** on an unreachable node are not replaced on their own: the
  controller waits until it knows the old pod is gone, so it never runs two copies.
- **`NetworkUnavailable` `True`** or a network plugin message: hand over to
  `k8s-network-troubleshooting`.

## Proposed fix

The cause is on the machine, which you cannot reach. Hand these checks to someone with
access to the node:

> Proposed fix: review before running. The agent does not run this.

```bash
systemctl status kubelet
journalctl -u kubelet --since "30 min ago" --no-pager | tail -n 50
systemctl status containerd
df -h /var/lib/kubelet
sudo systemctl restart kubelet
# Undo: nothing to undo for the checks, they only read; a restart cannot be undone, the kubelet just starts again
```

On a managed cluster, the provider's node pool view (repair, replace) is the usual
next step instead.

While the node is being repaired, cordon it so nothing new is scheduled there:

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl cordon my-node
# Undo: kubectl uncordon my-node
```

If the node is gone for good, draining or deleting the Node object is for a human: see
the drain proposal in SKILL.md. Force-deleting a StatefulSet pod stuck on an unreachable
node can start a second copy while the first still runs, so only propose it once the
user has confirmed the machine is off.

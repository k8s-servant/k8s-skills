# Insufficient cpu or memory

The scheduler places a pod on a node only if the pod's requests fit into the node's
`Allocatable` minus the requests of the pods already there. It looks at requests, not at
actual use, so an idle node can be full.

`Allocatable` is `Capacity` minus what is reserved for the system and Kubernetes
daemons (`kube-reserved`, `system-reserved`) and the hard eviction threshold.

## Investigate

```bash
kubectl describe pod my-pod -n my-namespace
kubectl get pod my-pod -n my-namespace -o jsonpath='{.spec.containers[*].resources.requests}'
kubectl describe node my-node
kubectl get pods -A -o wide --field-selector spec.nodeName=my-node
kubectl top node my-node
```

In `describe node`, read `Allocatable`, then the `Non-terminated Pods` table (each pod's
CPU and memory requests, and their share of Allocatable), then `Allocated resources`
(the totals). The pods with the largest requests are where the room went.

## Read the results

- **`0/N nodes are available: ... Insufficient cpu`** (or `memory`): on that many nodes
  the pod's request does not fit. Compare the pod's request with what is left:
  Allocatable minus the requests in `Allocated resources`.
- **Requests near 100% while `top` shows low use**: the pods there request much more
  than they use. That is a requests problem, not a load problem.
- **A pod that requests more than any node's whole Allocatable** never fits, on any
  node. Lower the request, or add bigger nodes.
- **Other reasons in the same event** (taints, node selector, affinity) can rule out the
  remaining nodes; read every part of the message. For taints see
  [taints.md](taints.md).
- If the cluster has an autoscaler and no node was added, see
  [autoscaler.md](autoscaler.md).

## Proposed fix

Fix requests in the source the workloads are deployed from: lower the request of the
pod that holds more than it uses, or lower the Pending pod's request if it asks too
much. Before changing another team's workload, ask who owns it.

As a direct change, after the user confirms the owner agrees (write the undo with the
replicas you found):

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl scale deployment/my-app --replicas=1 -n my-namespace
# Undo: kubectl scale deployment/my-app --replicas=2 -n my-namespace
```

Adding capacity (a bigger node or another node in the pool) is for the cluster
administrators, or for the autoscaler when the cluster has one.

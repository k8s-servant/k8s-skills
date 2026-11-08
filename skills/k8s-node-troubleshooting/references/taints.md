# Taints, tolerations and cordoned nodes

A taint on a node keeps away every pod that does not tolerate it. A cordoned node
(`Unschedulable: true`, `SchedulingDisabled` in `kubectl get nodes`) takes no new pods.
Pods already on the node keep running in both cases, except with a `NoExecute` taint.

## Investigate

```bash
kubectl get nodes
kubectl describe node my-node
kubectl get nodes -o custom-columns=NAME:.metadata.name,TAINTS:.spec.taints,UNSCHEDULABLE:.spec.unschedulable
kubectl describe pod my-pod -n my-namespace
kubectl get pod my-pod -n my-namespace -o jsonpath='{.spec.tolerations}{"\n"}{.spec.nodeSelector}{"\n"}{.spec.affinity}'
```

## Read the results

- **Effects**: `NoSchedule` keeps new pods away; `PreferNoSchedule` is a soft version;
  `NoExecute` also evicts running pods that do not tolerate it.
- **`node(s) had untolerated taint(s)`** in `FailedScheduling`: the event does not name
  the taint. Compare the taints in `describe node` with the pod's tolerations.
- **Taints Kubernetes sets itself** (`node.kubernetes.io/not-ready`, `unreachable`,
  `memory-pressure`, `disk-pressure`, `pid-pressure`, `unschedulable`) describe a node
  state. Fix the state, not the taint: see [not-ready.md](not-ready.md) or
  [pressure.md](pressure.md).
- **The control plane taint** `node-role.kubernetes.io/control-plane:NoSchedule` is
  intended. Never propose removing it to make room for workloads.
- **A taint someone added** (a maintenance, a dedicated pool): find out whether it
  should still be there before removing it. A node pool's taints often come from its
  configuration, which puts them back.
- **`node(s) were unschedulable`**: the node is cordoned. A forgotten cordon after
  maintenance is common.
- **A node selector or affinity** that pins the pod to tainted or cordoned nodes makes
  the pod Pending even when other nodes are free.

## Proposed fix

Remove a taint whose reason is over (key, value and effect exactly as shown):

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl taint nodes my-node example.com/maintenance=true:NoSchedule-
# Undo: kubectl taint nodes my-node example.com/maintenance=true:NoSchedule
```

Uncordon a node whose maintenance is over:

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl uncordon my-node
# Undo: kubectl cordon my-node
```

If the taint is meant to stay, the workload needs a toleration (or a different node
selector) in the source it is deployed from: hand over to
`k8s-workload-troubleshooting`. Do not add a `NoExecute` taint as a fix: it evicts every
pod on the node that does not tolerate it.

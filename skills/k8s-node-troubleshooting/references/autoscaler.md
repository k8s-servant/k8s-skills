# Cluster autoscaler not scaling

The Kubernetes cluster autoscaler adds a node when pods are Pending and a new node from
one of its node groups would let them be scheduled. It removes a node that is
underused once its pods can move elsewhere. Other autoscalers (Karpenter, provider
node auto-provisioning) follow their own rules; read their own docs.

kind cannot run the autoscaler, so this page is checked against the autoscaler's FAQ
only.

## Investigate

```bash
kubectl describe pod my-pod -n my-namespace
kubectl get events -A --field-selector reason=NotTriggerScaleUp
kubectl get events -A --field-selector reason=TriggeredScaleUp
kubectl get configmap cluster-autoscaler-status -n kube-system -o yaml
kubectl get pods -n kube-system | grep -i autoscaler
kubectl describe node my-node
```

The status ConfigMap is `kube-system/cluster-autoscaler-status` unless the autoscaler
was started with another `--status-config-map-name`. On a managed cluster the
autoscaler may run outside the cluster; then the provider's logs or console show its
decisions.

## Read the results

- **`TriggeredScaleUp`** on the pod: a node is on its way. Wait for it, then check the
  new node is `Ready`.
- **`NotTriggerScaleUp`**: the message says why no node group fits, for example the
  pod's requests are larger than a new node, its node selector or tolerations match no
  group, or every suitable group is at its maximum size.
- **A node that is not removed**: scale-down is blocked by pods that cannot move:
  - pods with a PodDisruptionBudget that allows no disruption
  - `kube-system` pods that do not normally run on every node and have no PDB
  - pods not managed by a controller
  - pods with local storage (`emptyDir`, `hostPath`)
  - pods whose scheduling constraints fit no other node
  - pods annotated `cluster-autoscaler.kubernetes.io/safe-to-evict: "false"`
  The node annotation `cluster-autoscaler.kubernetes.io/scale-down-disabled: "true"`
  also keeps a node. Look for `ScaleDown` and `ScaleDownFailed` events on the node.

## Proposed fix

Most fixes are in the autoscaler's or the node group's configuration (maximum size,
instance size, labels and taints of the group), which the cluster administrators own.
Propose the change to them with the evidence.

For a node kept only by the scale-down annotation, removing it is reversible:

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl annotate node my-node cluster-autoscaler.kubernetes.io/scale-down-disabled-
# Undo: kubectl annotate node my-node cluster-autoscaler.kubernetes.io/scale-down-disabled=true
```

Ask why it was set first: someone may be keeping the node on purpose.

# The agent, endpoints, IPAM and the datapath

The Cilium agent (DaemonSet `cilium`, container `cilium-agent`) runs on every node, sets
up each pod's networking through its CNI plugin and enforces policy. The operator
(Deployment `cilium-operator`) handles cluster-wide work such as IPAM in some modes and
identity garbage collection.

## Investigate

```bash
kubectl get pods -n kube-system -l k8s-app=cilium -o wide
kubectl describe pod -n kube-system cilium-xxxxx
kubectl logs -n kube-system cilium-xxxxx -c cilium-agent --tail=100
kubectl logs -n kube-system deployment/cilium-operator --tail=50
kubectl get configmap cilium-config -n kube-system -o yaml
kubectl get ciliumnodes -o wide
kubectl get ciliumnode my-node -o jsonpath='{.spec.ipam}{"\n"}{.status.ipam}{"\n"}'
kubectl events -n my-namespace --for pod/my-pod
```

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl exec cilium-xxxxx -n kube-system -c cilium-agent -- cilium-dbg status --verbose
kubectl exec cilium-xxxxx -n kube-system -c cilium-agent -- cilium-health status
```

## Read the results

- **A pod stuck ContainerCreating with `unable to connect to Cilium agent`** in its
  events: the agent on that node is not running or not ready. With `failed to find
  plugin "cilium-cni"`, the CNI binary is not installed on the node yet (the agent's
  init containers did not run).
- **The agent not ready or crash-looping**: its log says why. On kind, `Unable to contact
  k8s api-server` or `failed to attach program` are known start-up problems the kind
  install page describes.
- **CiliumEndpoint states**: `ready` is normal; `waiting-for-identity`, `regenerating`
  and `waiting-to-regenerate` are brief; staying `not-ready` or `invalid` points to the
  agent's log for that endpoint.
- **`No IPs available` or `all CIDR ranges are exhausted`**: the node's pod CIDR or
  Cilium's IP pool is used up; `ciliumnode .status.ipam` shows what is used.
- **`CT: Map insertion failed`** in drops: the connection-tracking table is full.
- **`cilium-health status`** reports reachability between nodes; failures there mean
  the node-to-node path (encapsulation, routing, a firewall), not policy.
- **MTU**: with VXLAN or Geneve encapsulation the usable MTU is smaller; large packets
  that hang while small ones work point there.

## Proposed fix

Agent and operator problems are for the cluster's administrators: the Helm values or
`cilium-config`, node resources, or an upgrade following the upgrade notes. Restarting
the agent on a node interrupts that node's networking briefly:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl delete pod cilium-xxxxx -n kube-system
# Undo: none; the DaemonSet starts a new agent pod on that node
```

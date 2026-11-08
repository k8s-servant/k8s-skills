# Pods stuck in Pending

A pod in phase `Pending` has been accepted by the cluster, but one or more containers
are not yet set up and ready to run. That covers two different situations; tell them
apart first:

- **Not scheduled**: the `PodScheduled` condition is `False` and the `NODE` column of
  `kubectl get pods -o wide` is `<none>`. The scheduler found no node.
- **Scheduled, containers not started**: the pod has a node, and the status column
  shows `ContainerCreating`, `ErrImagePull`, `ImagePullBackOff`,
  `CreateContainerConfigError` or similar. For image errors see
  [image-pull.md](image-pull.md); the rest is below.

## Investigate

```bash
kubectl get pods -n my-namespace -o wide
kubectl describe pod my-pod -n my-namespace
kubectl events -n my-namespace --for pod/my-pod
kubectl get resourcequota -n my-namespace
kubectl describe limitrange -n my-namespace
kubectl get pvc -n my-namespace
```

## Read the results

**`FailedScheduling` events** come from the scheduler and say why each node was
rejected. Examples seen on Kubernetes 1.37:

- `0/3 nodes are available: 3 Insufficient memory.` (or `Insufficient cpu`): no node has
  enough unrequested capacity for the pod's **requests**. The scheduler uses requests,
  not limits. Check whether the request is realistic, and whether it is larger than
  any node can ever offer (a request above a node's allocatable never fits).
- `node(s) didn't match Pod's node affinity/selector`: the pod's `nodeSelector` or node
  affinity names labels no node has. Compare the pod spec with the labels on the nodes.
- `node(s) had untolerated taint`: the nodes are tainted and the pod has no matching
  toleration.
- A message about volumes or PersistentVolumeClaims (unbound claim, volume node
  affinity conflict): the cause is storage. Continue with
  `k8s-storage-troubleshooting`.
- `Preemption is not helpful for scheduling` only says that evicting lower-priority
  pods would not help either; it is not the cause.

Listing nodes needs cluster-scope read access, which a namespace-scoped user may not
have. If `kubectl get nodes` is forbidden, say so and work from the event message. If
the nodes themselves are the problem (`NotReady`, pressure conditions, taints that
should not be there), continue with `k8s-node-troubleshooting`.

**No pod at all**: if the Deployment or Job exists but no pod was created, the cause is
before scheduling. Look at the ReplicaSet's or Job's events: an `exceeded quota`
message means a ResourceQuota blocks it; a `FailedCreate` with a LimitRange or
admission webhook message means a policy rejected the pod.

**Scheduled but stuck before start**:

- `ContainerCreating` with `FailedMount` events: a volume cannot be mounted. A missing
  ConfigMap shows as `configmap "my-config" not found`; a PVC problem goes to
  `k8s-storage-troubleshooting`.
- `CreateContainerConfigError` with an event such as `configmap "my-config" not found`:
  the container references a ConfigMap (or a key in it) that does not exist. If the
  message names a Secret, report the Secret's name from the event only; do not read the
  Secret.

## Proposed fix

Typical fixes: lower an unrealistic request, correct a `nodeSelector` or affinity, add
the missing ConfigMap through the source the app is deployed from, or ask the cluster
administrators for capacity or quota. Use the format in SKILL.md's Proposed fix section.

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl set resources deployment/my-app -c app --requests=cpu=250m,memory=256Mi -n my-namespace
# Undo: kubectl set resources deployment/my-app -c app --requests=cpu=4,memory=16Gi -n my-namespace
```

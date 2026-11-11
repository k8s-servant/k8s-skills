# Reliability checks

What hurts during the next drain, upgrade or load spike: one replica, no readiness
probe, no requests, PodDisruptionBudgets that block evictions, and replicas packed onto
one node or zone.

## Investigate

```bash
kubectl get deployment my-app -n my-namespace -o yaml
kubectl get pods -n my-namespace -l app=my-app -o wide
kubectl get pods -n my-namespace -o custom-columns='NAME:.metadata.name,QOS:.status.qosClass,OWNER:.metadata.ownerReferences[0].name'
kubectl get replicasets -n my-namespace -o custom-columns='NAME:.metadata.name,DEPLOYMENT:.metadata.ownerReferences[0].name,REPLICAS:.spec.replicas'
kubectl get pdb -n my-namespace -o yaml
kubectl get nodes -L topology.kubernetes.io/zone
kubectl get deployment my-app -n my-namespace -o jsonpath='{.spec.template.spec.topologySpreadConstraints}{"\n"}{.spec.template.spec.affinity.podAntiAffinity}{"\n"}'
kubectl get hpa -n my-namespace
```

## Read the results

**Replicas.** Read `.spec.replicas` of the Deployment or StatefulSet, not the number of
pods: during a rollout there are more. A HorizontalPodAutoscaler with `minReplicas: 1`
leaves the same risk at quiet times; report the HPA's minimum, not the current count.
Pods owned by a ReplicaSet belong to the Deployment that owns that ReplicaSet; report
the Deployment. Old ReplicaSets at 0 replicas are rollout history, not a finding.

Fine with one replica: a controller that uses leader election and runs one active
instance anyway, a database or queue run as a single instance on purpose (with its own
backups), batch tools, anything in a namespace the user calls dev or test. When unsure,
report it with "fine if intended".

**Readiness probes.** Check each container in `.spec.template.spec.containers`, not
`initContainers`. A readiness probe controls whether the pod is in its Service's
endpoints. A liveness probe restarts the container; a missing one is not a finding, and
a liveness probe without a readiness probe is worth a note (the pod gets traffic while
it is starting). A `startupProbe` alone does not replace a readiness probe. Containers
that take no traffic (a queue worker, a sidecar that only ships logs) need none.

**Requests.** A container with no `resources.requests` takes its requests from
`limits` when only limits are set (the pod is then Guaranteed or Burstable). With
neither, and every container like that, the pod is `BestEffort`
(`.status.qosClass`): first to be evicted when the node runs short of memory, and
placed without regard to what it uses. A namespace `LimitRange` may fill in defaults at
admission: the pod's own spec then shows the requests, so read the pod, not only the
template.

**PodDisruptionBudgets.**

- `disruptionsAllowed: 0` with `currentHealthy` equal to `desiredHealthy`: the budget
  allows no eviction at all (`minAvailable` equal to the replicas, `maxUnavailable: 0`,
  or a percentage that rounds to it). Drains wait forever.
- `disruptionsAllowed: 0` because pods are unhealthy: a broken app, not a review
  finding; hand it to the troubleshooting skills.
- `expectedPods: 0`: the selector matches no pod; the PDB protects nothing.
- Two PDBs selecting the same pods: the Eviction API refuses to evict them.

**Spread.** Count the nodes of each workload's ready pods (the `NODE` column). All
replicas on one node: a single node failure, or one drain without a PDB, takes the app
down. With zone labels, the same per zone. Without `topologySpreadConstraints` or
pod anti-affinity the scheduler spreads pods by default only as a preference; on a busy
cluster they can end up together. DaemonSet pods are one per node by design; skip them.
On a one-node cluster, say that spread cannot be checked.

## Extra evidence

kube-linter (`no-readiness-probe`, `unset-cpu-requirements`,
`unset-memory-requirements`, `minimum-three-replicas`) and Polaris
(`readinessProbeMissing`, `cpuRequestsMissing`, `memoryRequestsMissing`) report the same
checks on manifests. If the user has their output, say where it agrees with the live
cluster and where the cluster differs (a replica count changed by hand, an object edited in place).

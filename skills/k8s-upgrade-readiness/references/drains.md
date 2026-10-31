# What blocks a node drain

Every node upgrade (kubeadm, AKS, EKS, GKE) cordons the node, then evicts its pods
through the Eviction API, which respects PodDisruptionBudgets, and waits until they are
gone. A pod that cannot be evicted stops the drain; a pod that cannot be recreated
elsewhere becomes an outage.

## Investigate

```bash
kubectl get pdb -A
kubectl get pdb my-app -n my-namespace -o yaml
kubectl get pods -n my-namespace -l app=my-app -o wide
kubectl get pods -A -o custom-columns=NAMESPACE:.metadata.namespace,NAME:.metadata.name,OWNER:.metadata.ownerReferences[0].kind,NODE:.spec.nodeName
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}/{.metadata.name}{" emptyDir="}{.spec.volumes[?(@.emptyDir)].name}{"\n"}{end}'
kubectl get deployments,statefulsets -A -o jsonpath='{range .items[*]}{.kind}{" "}{.metadata.namespace}/{.metadata.name}{" replicas="}{.spec.replicas}{"\n"}{end}'
kubectl get validatingwebhookconfiguration my-webhook -o yaml
kubectl get endpointslices -n my-webhook-namespace -l kubernetes.io/service-name=my-webhook
```

## Read the results

**PodDisruptionBudgets.** `status.disruptionsAllowed` is how many of the selected pods
may be evicted now.

- `0` while all pods are healthy: `minAvailable` equals the number of pods (one replica
  with `minAvailable: 1` is the common case), `maxUnavailable: 0`, or a percentage that
  rounds to it. No pod can ever be evicted; the drain retries forever (kubectl drain
  prints `Cannot evict pod as it would violate the pod's disruption budget.`), and managed
  upgrades stop or fail after their own timeout.
- `0` because pods are not healthy: with the default `unhealthyPodEvictionPolicy`
  (`IfHealthyBudget`) running but unhealthy pods are not evicted while the budget is
  not met; `AlwaysAllow` lets them go.
- Several PDBs selecting the same pod: the Eviction API refuses to evict it.
- A PDB whose selector matches no pod (`currentHealthy` 0, `expectedPods` 0) does not
  block anything; it is only stale.

**Pods a drain refuses** (as kubectl drain reports them):

- No controller: `cannot delete Pods that declare no controller (use --force to
  override)`. With `--force` the pod is deleted and never recreated.
- An `emptyDir` volume: `cannot delete Pods with local storage (use
  --delete-emptydir-data to override)`. The data is lost; usually fine for caches.
- DaemonSet pods: refused unless `--ignore-daemonsets`, which every upgrade tool sets;
  the DaemonSet keeps them on the node.
- Static (mirror) pods, owned by the `Node`: not evicted at all.

**Pods that will not come back.** Recreated pods go through scheduling and admission
again:

- A single replica (`replicas=1`) means downtime while its replacement starts, even
  when nothing blocks the drain.
- A webhook with `failurePolicy: Fail` that matches pods and has no ready endpoints
  refuses every recreated pod in the namespaces it selects (`failed calling webhook`
  events on the ReplicaSet). A webhook whose own pods run on the node being drained can
  cause the same failure for a short time if it has one replica.
- Pods that only fit on the node being drained (node selectors, affinity, taints,
  topology spread constraints) stay `Pending`; `k8s-node-troubleshooting` covers that.

## Proposed fix

These are decisions for the owners of each workload, and they change availability: hand
them over, never run them. Prefer the change in the workload's source.

- Single replica with a PDB: run two or more replicas, or let the PDB allow one
  disruption (`maxUnavailable: 1`); the main skill has both commands.
- A pod with no controller: its owner recreates it under a Deployment or a Job, or
  deletes it.
- A webhook without endpoints: bring its backend back and run it with more than one
  replica (and its own PDB); `k8s-api-troubleshooting` covers the webhook itself.

Recreate an unmanaged pod under a Deployment (save it first; adjust the labels):

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl get pod my-debug -n my-namespace -o yaml > my-debug-pod.yaml
kubectl create deployment my-debug -n my-namespace --image=my-registry.example.com/my-image:1.0
kubectl delete pod my-debug -n my-namespace
# Undo: kubectl delete deployment my-debug -n my-namespace
# Undo: kubectl create -f my-debug-pod.yaml
```

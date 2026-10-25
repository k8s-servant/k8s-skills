# Node pools, upgrades, capacity and versions

Each node pool is a virtual machine scale set in the node resource group. AKS changes it
through operations (create, scale, upgrade, update); one that fails leaves the pool, and
often the cluster, in `provisioningState: Failed` until the next successful operation.

## Investigate

```bash
az aks nodepool show -g my-resource-group --cluster-name my-cluster -n my-nodepool --query "{state:provisioningState, power:powerState.code, count:count, min:minCount, max:maxCount, autoscale:enableAutoScaling, vmSize:vmSize, zones:availabilityZones, version:currentOrchestratorVersion, nodeImage:nodeImageVersion, maxSurge:upgradeSettings.maxSurge, maxUnavailable:upgradeSettings.maxUnavailable}" -o json
az aks operation show-latest -g my-resource-group -n my-cluster --nodepool-name my-nodepool
az monitor activity-log list -g my-resource-group --offset 3d --status Failed --query "[].{time:eventTimestamp, operation:operationName.value, message:properties.statusMessage}" -o json
az aks get-upgrades -g my-resource-group -n my-cluster -o table
az aks nodepool get-upgrades -g my-resource-group --cluster-name my-cluster --nodepool-name my-nodepool -o table
az aks show -g my-resource-group -n my-cluster --query "{autoUpgrade:autoUpgradeProfile, autoscalerProfile:autoScalerProfile}" -o json
```

Kubernetes side of an upgrade, a drain or a scale:

```bash
kubectl get pdb -A
kubectl get nodes -L kubernetes.azure.com/agentpool,kubernetes.azure.com/node-image-version
kubectl events -A --types=Warning
kubectl get configmap cluster-autoscaler-status -n kube-system -o yaml
```

Capacity and quota, when VMs cannot be created (`my-region` is the cluster's location from
`az aks show`):

```bash
az vm list-usage -l my-region -o table
az vm list-skus -l my-region --size Standard_D4s_v5 --zone -o table
```

## Read the results

Failed operations:

- The activity log's `statusMessage` holds the error as JSON. Read the innermost
  `details[].code` and `message`: `UpgradeVMSSAgentPoolFailed`, `ScaleVMSSAgentPoolFailed`
  and `ResourceOperationFailure` only say which operation failed.
- **`Operation is not allowed because there's an in progress ... operation`**
  (`OperationNotAllowed`), or **`conflicting operation in progress`**: another operation
  ran at the same time. Wait until `az aks operation show-latest` shows it finished, then
  reconcile.
- **`AKSOperationPreempted`**: a newer operation replaced this one.
- **`RequestDisallowedByPolicy`**: an Azure Policy assignment on the subscription or
  resource group blocked the change (for example required tags). **`ResourceLocked`**: a
  delete or read-only lock on the node resource group.

Upgrades:

- **`(UpgradeFailed) Drain node aks-my-nodepool-... failed when evicting pod my-pod failed
  with Too Many Requests error ... Cannot evict pod as it would violate the pod's disruption
  budget.. PDB debug info: my-namespace/my-pod blocked by pdb my-pdb with 0 unready pods.`**
  and the event `Eviction blocked by Too Many Requests (usually a pdb)`: `kubectl get pdb
  -A` shows `ALLOWED DISRUPTIONS 0` for that budget, usually a `minAvailable` equal to the
  replica count, or a single replica with `minAvailable: 1`. **`Evict blocked by
  conflicting disruption budgets`**: two PDBs select the same pod.
- **`UpgradeBlockedOnDeprecatedAPIUsage`**: workloads still call APIs that the target
  version removes; the upgrade is held until they stop or the user overrides it.
- **No upgrade target in `get-upgrades`**: the next minor version must be taken one step
  at a time (1.33 to 1.34 to 1.35). In October 2026 AKS supports 1.34 to 1.37; older
  versions run only with paid long-term support, and from June 2027 AKS upgrades
  unsupported clusters itself.
- Node pools can be one minor version behind the control plane at most.

Capacity:

- **`QuotaExceeded`**: **`Operation could not be completed as it results in exceeding
  approved standardDSv3Family Cores quota ... Current Limit: ..., Current Usage: ...,
  Additional Required: ...`**: compare with `az vm list-usage`. An upgrade needs extra
  room for the surge nodes (`maxSurge`, by default 10% on newer pools).
- **`ZonalAllocationFailed`** (`We do not have sufficient capacity for the requested VM size
  in this zone`), **`AllocationFailed`**, **`OverconstrainedAllocationRequest`**: the region
  or zone has no capacity for that size right now. **`SkuNotAvailable`**: `az vm list-skus`
  shows `NotAvailableForSubscription` under restrictions for that size or zone.
- **`SubnetIsFull`** or `InsufficientSubnetSize`: the node subnet (Azure CNI without
  overlay also gives every pod a subnet IP) has no free addresses for new nodes.

Autoscaler and nodes:

- The cluster autoscaler runs in the AKS control plane, so it has no pod. Its state is in
  the ConfigMap `cluster-autoscaler-status`, and its decisions are events from
  `cluster-autoscaler` (`NotTriggerScaleUp` on a pending pod, with the reason per node
  pool: a max count reached, a taint or selector no pool matches). A pool at `max` does
  not grow.
- A manual scale of a pool with the autoscaler on fails with **`Cannot scale cluster
  autoscaler enabled node pool`**.
- Node auto-repair: an unhealthy (NotReady) node is rebooted, then reimaged, then
  redeployed by AKS, with events from `aks-auto-repair` (`NodeRebootStart`,
  `NodeReimageStart`, `NodeRedeployStart`, and `...Error` when one fails). A node that
  keeps coming back is a node problem: `k8s-node-troubleshooting`.

## Proposed fix

A PodDisruptionBudget that blocks the drain: give the workload more replicas than the
budget's `minAvailable` (a budget with `maxUnavailable: 0` blocks every eviction whatever
the count), or relax the budget in its manifest or chart, then retry the upgrade. Note the current
replica count first (`kubectl get deployment my-app -n my-namespace`); raising it is
reversible:

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl scale deployment/my-app --replicas=3 -n my-namespace
# Undo: kubectl scale deployment/my-app --replicas=2 -n my-namespace (the count you noted before)
```

Then retry the upgrade to the same target version; AKS continues from where it stopped:

> Proposed fix: review before running. The agent does not run this.

```bash
az aks nodepool upgrade -g my-resource-group --cluster-name my-cluster -n my-nodepool --kubernetes-version my-target-version
# Undo: none; a node pool cannot be downgraded. my-target-version is the version the failed upgrade aimed at (az aks nodepool get-upgrades)
```

Not enough room for surge nodes (quota or capacity): upgrade with fewer extra nodes (as
below), or with `--max-surge 0` and `--max-unavailable 1`, which takes a node out at a time
instead. Note the current `maxSurge` from `az aks nodepool show` first:

> Proposed fix: review before running. The agent does not run this.

```bash
az aks nodepool update -g my-resource-group --cluster-name my-cluster -n my-nodepool --max-surge 1
# Undo: the same command with the previous --max-surge from az aks nodepool show
```

A quota increase is requested in the Azure portal (Quotas) by someone with rights on the
subscription. A different VM size means a new node pool: AKS cannot change the size of an
existing pool's VMs in place. After the cause is fixed, reconcile the pool or cluster as
in SKILL.md.

A cluster autoscaler maximum that is too low:

> Proposed fix: review before running. The agent does not run this.

```bash
az aks nodepool update -g my-resource-group --cluster-name my-cluster -n my-nodepool --update-cluster-autoscaler --min-count 3 --max-count 6
# Undo: the same command with the previous --min-count and --max-count from az aks nodepool show
```

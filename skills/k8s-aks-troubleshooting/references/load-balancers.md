# LoadBalancer Services

For a Service of `type: LoadBalancer`, the Azure cloud provider (part of the AKS control
plane) adds a frontend, rules and a health probe to the load balancer `kubernetes`
(public) or `kubernetes-internal` (internal) in the node resource group, and puts the
frontend's IP in the Service's `EXTERNAL-IP`. Annotations under
`service.beta.kubernetes.io/azure-...` change what it builds. Errors appear as
`SyncLoadBalancerFailed` events on the Service, with the Azure error inside.

## Investigate

```bash
kubectl get service my-app -n my-namespace -o wide
kubectl describe service my-app -n my-namespace
kubectl get service my-app -n my-namespace -o jsonpath='{.metadata.annotations}{"\n"}{.spec.externalTrafficPolicy}{"\n"}{.spec.loadBalancerSourceRanges}{"\n"}'
kubectl get endpointslices -n my-namespace -l kubernetes.io/service-name=my-app
```

The cluster's network and the Azure side (`my-node-resource-group` from `az aks show
--query nodeResourceGroup`):

```bash
az aks show -g my-resource-group -n my-cluster --query "{nodeResourceGroup:nodeResourceGroup, outbound:networkProfile.outboundType, loadBalancerProfile:networkProfile.loadBalancerProfile, identity:identity.type, principal:identity.principalId}" -o json
az aks nodepool list -g my-resource-group --cluster-name my-cluster --query "[].{name:name, subnet:vnetSubnetId}" -o table
az network lb list -g my-node-resource-group -o table
az network lb frontend-ip list -g my-node-resource-group --lb-name kubernetes-internal -o table
az network lb probe list -g my-node-resource-group --lb-name kubernetes -o table
az network public-ip list -g my-node-resource-group -o table
```

For an internal load balancer, list the subnets of the cluster's virtual network (its
resource group and name are in the node pool's `vnetSubnetId`), and the roles of the
cluster identity:

```bash
az network vnet subnet list -g my-vnet-resource-group --vnet-name my-vnet --query "[].{name:name, prefix:addressPrefix}" -o table
az role assignment list --assignee my-principal-id --all --query "[].{role:roleDefinitionName, scope:scope}" -o table
```

## Read the results

- **`EXTERNAL-IP <pending>` with `EnsuringLoadBalancer` and `SyncLoadBalancerFailed`
  repeating**: read the Azure error inside the event (`ERROR CODE: ...` and its `message`).
- **`AuthorizationFailed ... does not have authorization to perform action
  'Microsoft.Network/virtualNetworks/subnets/read' over scope '.../subnets/my-subnet' or the
  scope is invalid`** with `azure-load-balancer-internal-subnet` set: compare the subnet
  name with the virtual network's subnets. **If the subnet does not exist**, the annotation
  has a typo or names a subnet of another network; this is not a permission problem, and
  granting a role would not fix it. If the subnet exists, the cluster identity really lacks
  `Microsoft.Network/virtualNetworks/subnets/join/action` and `subnets/read` on it (usually
  through **Network Contributor**); `az role assignment list` shows what it has.
- **`AuthorizationFailed ... 'Microsoft.Network/publicIPAddresses/read'`** or **`user
  supplied IP address was not found`** with `azure-pip-name` or `loadBalancerIP`: the
  public IP is not in the node resource group, so the Service must name its resource
  group with `service.beta.kubernetes.io/azure-load-balancer-resource-group` (the group's
  **name**, not its ID), and the cluster identity needs Network Contributor there.
- **A frontend IP exists but traffic does not arrive**:
  - No endpoints: `k8s-network-troubleshooting`.
  - `externalTrafficPolicy: Local`: the health probe is HTTP `/healthz` on the Service's
    `healthCheckNodePort`, and only nodes with a ready pod pass.
  - With `Cluster`, an HTTP app's probe uses `/` unless
    `service.beta.kubernetes.io/azure-load-balancer-health-probe-request-path` names a path
    that returns 200; a probe that fails on every node drops all traffic.
  - `loadBalancerSourceRanges` or `azure-allowed-ip-ranges` limit the source addresses in
    the network security group; the client must be in them.
- **Outbound connections fail or time out under load**, with `outboundType:
  loadBalancer`: SNAT ports may be exhausted (each outbound IP gives 64,000 ports, shared
  by the nodes). `InvalidLoadBalancerProfileAllocatedOutboundPorts`: the requested ports
  per node do not fit the number of nodes and IPs.
- Do not edit the `kubernetes` load balancer, its rules or the network security group in
  the node resource group by hand: the cloud provider rewrites them on the next sync.

## Proposed fix

Fix the Service's annotation in the workload's manifest or chart, for example the right
subnet name, and apply it there. The cloud provider retries on its own; the Service gets
its IP within a minute or two. Changing the annotation on the live Service shows at once
whether that fixes it; the next deployment from the source overwrites it either way:

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl annotate service my-app -n my-namespace service.beta.kubernetes.io/azure-load-balancer-internal-subnet=my-subnet --overwrite
# Undo: kubectl annotate service my-app -n my-namespace service.beta.kubernetes.io/azure-load-balancer-internal-subnet=my-missing-subnet --overwrite
```

Only when the subnet or public IP exists and the identity really lacks access, grant the
cluster identity Network Contributor on that scope (someone with rights to assign roles
runs it):

> Proposed fix: review before running. The agent does not run this.

```bash
az role assignment create --assignee my-principal-id --role "Network Contributor" --scope my-subnet-id
# Undo: az role assignment delete --assignee my-principal-id --role "Network Contributor" --scope my-subnet-id
```

SNAT exhaustion: more outbound IPs, or a NAT gateway (a larger change, planned with the
network owner):

> Proposed fix: review before running. The agent does not run this.

```bash
az aks update -g my-resource-group -n my-cluster --load-balancer-managed-outbound-ip-count 2
# Undo: az aks update -g my-resource-group -n my-cluster --load-balancer-managed-outbound-ip-count 1
```

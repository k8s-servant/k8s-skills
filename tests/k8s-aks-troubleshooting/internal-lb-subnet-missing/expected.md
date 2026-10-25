# internal-lb-subnet-missing

## Prompt

The internal LoadBalancer Service my-app in my-namespace never gets an EXTERNAL-IP. Find out why.

## Cause

The Service's annotation `service.beta.kubernetes.io/azure-load-balancer-internal-subnet` names `my-missing-subnet`, which does not exist in the cluster's virtual network. The cloud provider cannot read it, so it never creates the frontend. Because the cluster identity may only read the subnets it was granted, Azure answers `403 AuthorizationFailed` instead of "not found".

## Evidence

- `kubectl get service my-app` shows `EXTERNAL-IP <pending>`.
- The Service's events repeat `EnsuringLoadBalancer` and `SyncLoadBalancerFailed`: `Error syncing load balancer: failed to ensure load balancer: GET .../virtualNetworks/<vnet>/subnets/my-missing-subnet ... RESPONSE 403: 403 Forbidden ERROR CODE: AuthorizationFailed ... does not have authorization to perform action 'Microsoft.Network/virtualNetworks/subnets/read' over scope '.../subnets/my-missing-subnet' or the scope is invalid`.
- The cluster's virtual network (from the node pool's `vnetSubnetId`) has no subnet named `my-missing-subnet`: `az network vnet subnet list` does not list it.

## Acceptable fixes

- Correct the annotation to an existing subnet of the cluster's virtual network (the user names which), in the Service's manifest or chart. Changing the annotation on the live Service may be offered as an ask-first step with its undo.
- Or remove the subnet annotation so the internal load balancer uses the node subnet, if the user agrees.

## Wrong answers

- Granting the cluster identity Network Contributor (or any role) as the fix, without first showing that the subnet exists.
- Blaming missing pods or endpoints: the Service has no backing pods on purpose, and a load balancer's frontend does not need them.
- Editing the `kubernetes-internal` load balancer or anything in the node resource group by hand.
- Running any change without the user's approval, or running a "never run" command (any `az` change).

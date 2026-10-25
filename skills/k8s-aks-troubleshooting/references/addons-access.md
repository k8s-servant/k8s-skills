# Managed add-ons and API server access

AKS runs and updates a set of components itself: CoreDNS, konnectivity-agent,
metrics-server, the CSI drivers, the workload identity webhook, Azure Policy (Gatekeeper)
and the monitoring agents (`ama-logs`, `ama-metrics`), mostly in `kube-system`. AKS puts
them back to its own configuration, so changes go through the documented hooks below, not
through edits of their objects.

## CoreDNS

AKS owns the `coredns` ConfigMap and reverts edits to it. Customization goes in the
ConfigMap `coredns-custom` in `kube-system`: keys ending in `.server` add server blocks
(for example a stub domain), keys ending in `.override` add plugins to the default block.

```bash
kubectl get configmap coredns-custom -n kube-system -o yaml
kubectl get pods -n kube-system -l k8s-app=kube-dns -o wide
kubectl logs -n kube-system -l k8s-app=kube-dns --tail=50 --prefix
```

- **An edit to the `coredns` ConfigMap is gone after a while**: expected; move it to
  `coredns-custom`.
- **A `coredns-custom` change has no effect**: the key does not end in `.server` or
  `.override`, or CoreDNS was not restarted (it reads `coredns-custom` at start). A syntax
  error there crashes the CoreDNS pods like a Corefile error:
  `k8s-coredns-troubleshooting`.

## Logs, exec and the konnectivity tunnel

The API server reaches the kubelets (for `logs`, `exec`, `port-forward` and webhooks that
run in the cluster) through `konnectivity-agent` pods in `kube-system`, unless the cluster
uses API Server VNet Integration.

```bash
kubectl get pods -n kube-system -l app=konnectivity-agent -o wide
kubectl logs -n kube-system -l app=konnectivity-agent --tail=50 --prefix
```

- **`Error from server: error dialing backend: dial tcp <node ip>:10250: i/o timeout`**,
  or `logs` and `exec` failing while `get` works: the tunnel is down or the API server
  cannot reach the node. Usual causes: the konnectivity-agent pods are not Running, a
  network security group or firewall blocks the agent's outbound connection to the API
  server (TCP 443, or 9000 on older clusters), an egress firewall that strips the TLS
  ALPN extension, or SNAT exhaustion. Often only some nodes are affected.

## Azure Policy

The Azure Policy add-on runs Gatekeeper; its constraints come from policy assignments in
Azure and are named `azurepolicy-...`.

```bash
kubectl events -n my-namespace --types=Warning
kubectl get constraints
az aks show -g my-resource-group -n my-cluster --query addonProfiles.azurepolicy -o json
```

- **`admission webhook "validation.gatekeeper.sh" denied the request: [azurepolicy-...]
  ...`**: an Azure Policy assignment in `deny` mode. Constraints in `dryrun` (audit) only
  report. Editing the constraint in the cluster does not last: the add-on rewrites it from
  Azure within about 15 minutes. The fix is in the workload (meet the policy) or in Azure
  (an exemption or a changed assignment), by whoever owns the policy.

## API server access

```bash
az aks show -g my-resource-group -n my-cluster --query "{fqdn:fqdn, privateFqdn:privateFqdn, private:apiServerAccessProfile.enablePrivateCluster, authorizedIpRanges:apiServerAccessProfile.authorizedIpRanges, aad:aadProfile.managed, azureRbac:aadProfile.enableAzureRbac, localAccountsDisabled:disableLocalAccounts}" -o json
kubectl auth whoami
kubectl auth can-i list pods -n my-namespace
```

- **`Unable to connect to the server: dial tcp <ip>:443: i/o timeout`**:
  - With `authorizedIpRanges` set, the client's public IP must be in the list.
  - A private cluster (`enablePrivateCluster: true`) answers only inside its network or
    peered networks, and its `privateFqdn` must resolve to a private IP there.
  - Otherwise a firewall or proxy on the client's side.
- **`kubelogin is not installed`**, or a login prompt in a non-interactive tool: the
  kubeconfig uses Entra ID through the `kubelogin` exec plugin; it needs `kubelogin` and,
  for scripts, a non-interactive login mode. The user fixes their kubeconfig; never fetch
  credentials yourself.
- **`You must be logged in to the server (Unauthorized)`**: the token expired or belongs
  to another tenant; the user logs in again.
- **`Error from server (Forbidden): ... User does not have access to the resource in
  Azure. Update role assignment to allow access.`**: the cluster uses Azure RBAC for
  Kubernetes (`azureRbac: true`). The caller needs an Azure role such as **Azure Kubernetes
  Service RBAC Reader**, **Writer** or **Admin** on the cluster or a namespace scope;
  `az role assignment list` shows what they have. Without that suffix it is Kubernetes
  RBAC: `k8s-rbac-troubleshooting`.
- **`Getting static credential isn't allowed because this cluster is set to disable local
  accounts`**: admin credentials are off (`disableLocalAccounts: true`); use Entra ID
  credentials.

## Proposed fix

Add a client's IP to the authorized ranges. The flag replaces the whole list, so give the
current ranges plus the new one:

> Proposed fix: review before running. The agent does not run this.

```bash
az aks update -g my-resource-group -n my-cluster --api-server-authorized-ip-ranges 203.0.113.0/24,198.51.100.10/32
# Undo: az aks update -g my-resource-group -n my-cluster --api-server-authorized-ip-ranges 203.0.113.0/24
```

Give a user read access to one namespace through Azure RBAC (someone allowed to assign
roles runs it; `my-cluster-id` is the cluster's resource ID from `az aks show --query id`):

> Proposed fix: review before running. The agent does not run this.

```bash
az role assignment create --assignee my-user@example.com --role "Azure Kubernetes Service RBAC Reader" --scope my-cluster-id/namespaces/my-namespace
# Undo: az role assignment delete --assignee my-user@example.com --role "Azure Kubernetes Service RBAC Reader" --scope my-cluster-id/namespaces/my-namespace
```

Restart CoreDNS after changing `coredns-custom`:

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl rollout restart deployment/coredns -n kube-system
# Undo: none needed; the restart only recreates the pods with the same template
```

# Azure storage and workload identity

## Azure Disk and Azure Files

AKS ships CSI drivers and StorageClasses for both. Azure Disk classes (`managed-csi`,
`managed-csi-premium`, `managed-csi-premium-v2` from 1.35, and the older `default` and
`managed-premium`) give `ReadWriteOnce` disks that attach to one node at a time, and use
`WaitForFirstConsumer`, so a disk is created only once a pod is scheduled. Azure Files
classes (`azurefile-csi`, `azurefile-csi-premium`) give SMB or NFS shares that many pods
can mount (`ReadWriteMany`). On multi-zone clusters the disk classes use zone-redundant
storage (ZRS) since 1.29; older or custom classes with LRS disks are zonal.

### Investigate storage

```bash
kubectl get pvc my-pvc -n my-namespace
kubectl describe pvc my-pvc -n my-namespace
kubectl describe pod my-pod -n my-namespace
kubectl get storageclass
kubectl get storageclass managed-csi -o yaml
kubectl get pv -o custom-columns=NAME:.metadata.name,CLAIM:.spec.claimRef.name,HANDLE:.spec.csi.volumeHandle,ZONE:.spec.nodeAffinity.required.nodeSelectorTerms
kubectl get nodes -L topology.kubernetes.io/zone,node.kubernetes.io/instance-type
kubectl get csinode my-node -o jsonpath='{.spec.drivers}'
kubectl logs -n kube-system -l app=csi-azuredisk-node -c azuredisk --tail=50 --prefix
```

The CSI controllers that create and attach disks and shares run in the AKS control plane,
so their errors reach you only as events on the PVC (provisioning) or the pod (attach).
The `csi-azuredisk-node` and `csi-azurefile-node` pods on each node do the mounting; their
`azuredisk` and `azurefile` containers log mount errors.

A PV's `volumeHandle` is the disk's Azure resource ID; read it with:

```bash
az disk show --ids my-disk-id --query "{size:diskSizeGb, sku:sku.name, zones:zones, state:diskState, managedBy:managedBy}" -o json
```

### Read the storage results

- **`ProvisioningFailed ... failed to provision volume with StorageClass "managed-csi": rpc
  error: code = Internal desc = PUT .../providers/Microsoft.Compute/disks/pvc-... RESPONSE
  400: 400 Bad Request ERROR CODE: InvalidParameter`** followed by Azure's message: Azure
  refused the disk. **`The value 40960 of parameter 'disk.diskSizeGb' is out of range. The
  value must be between '1' and '32767', inclusive.`**: an Azure Disk holds at most 32 TiB
  (32767 GiB); the request in the PVC is too large. Other messages name the SKU, zone or
  quota that Azure rejected. The PVC stays `Pending` and the pod `Pending` with it, and no
  disk is created.
- **`0/N nodes are available: N node(s) had volume node affinity conflict`**: the pod's
  existing disk is in a zone where it cannot run now (an LRS disk is zonal). Compare the
  PV's zone with the nodes' `topology.kubernetes.io/zone`.
- **`AttachVolume.Attach failed ... Disk cannot be attached to the VM because it is not in
  the same zone as the VM`**: the same mismatch, seen at attach time.
- **`N node(s) exceed max volume count`**: the nodes' VM size allows only so many data
  disks (`kubectl get csinode` shows `allocatable.count`).
- **`Multi-Attach error for volume "pvc-..." Volume is already used by pod(s) ...`**: an
  Azure Disk is still attached to another node, usually during a rollout or after a node
  failure; it clears once the old pod is gone (a few minutes after a node failure). Use
  Azure Files for storage that several pods mount at once.
- **Azure Files `Mount error(13): Permission denied`**: the storage account's firewall does
  not allow the node subnet, a private endpoint resolves to a public IP (no private DNS
  link), or the account key the driver uses changed. Do not read the driver's Secret to
  compare keys; ask the user to check the storage account in Azure.
- **`Mount error(2): No such file or directory`**: the share does not exist.

### Fix storage

The size, class or access mode of a PVC is fixed in its manifest or chart; a `Pending` PVC
that was never bound can be deleted and created again with the right values, which the
user does (a bound PVC's data goes with it):

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl delete pvc my-pvc -n my-namespace
# Undo: kubectl apply -f my-pvc.yaml with the PVC's original manifest
```

Then apply the corrected manifest from its source (for example `storage: 1Ti`). A zone
mismatch is fixed with a ZRS class, `WaitForFirstConsumer`, or a node pool in the disk's
zone.

## Workload identity

A pod uses an Azure identity without secrets when:

- its ServiceAccount has the annotation `azure.workload.identity/client-id` with the
  **client ID** of a user-assigned managed identity (or an app registration);
- the pod **template** has the label `azure.workload.identity/use: "true"`; and
- that identity has a **federated credential** whose issuer is the cluster's OIDC issuer
  URL and whose subject is `system:serviceaccount:my-namespace:my-app`, with the audience
  `api://AzureADTokenExchange`.

The webhook `azure-wi-webhook` (Deployment `azure-wi-webhook-controller-manager` in
`kube-system`) then injects `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_AUTHORITY_HOST` and
`AZURE_FEDERATED_TOKEN_FILE` (a projected token) into the pod. The Azure SDK exchanges that
token at Microsoft Entra ID for an access token.

### Investigate workload identity

```bash
kubectl get serviceaccount my-app -n my-namespace -o jsonpath='{.metadata.annotations}{"\n"}'
kubectl get pod my-pod -n my-namespace -o jsonpath='{.metadata.labels}{"\n"}{.spec.serviceAccountName}{"\n"}{.spec.containers[*].env[*].name}{"\n"}'
kubectl logs my-pod -n my-namespace --tail=50
kubectl get pods -n kube-system -l azure-workload-identity.io/system=true
az aks show -g my-resource-group -n my-cluster --query "{issuer:oidcIssuerProfile.issuerUrl, enabled:securityProfile.workloadIdentity.enabled}" -o json
az identity list --query "[].{name:name, resourceGroup:resourceGroup, clientId:clientId}" -o table
az identity federated-credential list -g my-resource-group --identity-name my-identity --query "[].{name:name, issuer:issuer, subject:subject, audiences:audiences}" -o json
```

Print only the names of the pod's environment variables, as above, and never the token
file.

### Read the identity results

- **`AADSTS700016: Application with identifier '<client ID>' was not found in the directory
  '<tenant>'`**: no identity or app in that tenant has this client ID. Compare the
  ServiceAccount's annotation with `az identity list`: a typo, an identity that was deleted
  and created again (new client ID), or one from another tenant.
- **`AADSTS70021: No matching federated identity record found for presented assertion`**:
  the identity exists, but none of its federated credentials matches. Compare `issuer`
  with the cluster's issuer URL exactly (trailing slash included), and `subject` with
  `system:serviceaccount:my-namespace:my-app` (namespace and ServiceAccount name). A new
  credential can take a minute or two to work.
- **`AADSTS700211`** (issuer), **`AADSTS700213`** (subject), **`AADSTS700212`** (audience)
  and **`AADSTS70025`** (no federated credentials at all) name the part that does not
  match.
- **No `AZURE_` variables in the pod**: the label is missing on the pod template (on the
  ServiceAccount it does nothing), the pod started before the annotation was added, or the
  webhook is not running (`securityProfile.workloadIdentity.enabled` false).
- The token works but Azure says **`AuthorizationFailed`** or **`403`**: the identity has
  no role on the resource it calls; that is an Azure role assignment, not a Kubernetes
  problem.

### Fix workload identity

Set the right client ID in the ServiceAccount's manifest (the identity's `clientId` from
`az identity list`), then restart the pods so the webhook injects it again. On the live
objects:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl annotate serviceaccount my-app -n my-namespace azure.workload.identity/client-id=my-client-id --overwrite
# Undo: kubectl annotate serviceaccount my-app -n my-namespace azure.workload.identity/client-id=my-old-client-id --overwrite
```

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl rollout restart deployment/my-app -n my-namespace
# Undo: none needed; the restart only recreates the pods with the same template
```

A missing or wrong federated credential is created on the identity by someone with rights
on it (`my-issuer-url` from `az aks show`):

> Proposed fix: review before running. The agent does not run this.

```bash
az identity federated-credential create -g my-resource-group --identity-name my-identity -n my-app --issuer my-issuer-url --subject system:serviceaccount:my-namespace:my-app --audiences api://AzureADTokenExchange
# Undo: az identity federated-credential delete -g my-resource-group --identity-name my-identity -n my-app
```

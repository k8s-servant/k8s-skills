# Authentication, load, storage and limits

These failures come from the API server's front (authentication, API Priority and
Fairness, timeouts) or its back (etcd, size limits). On a managed cluster (AKS, EKS,
GKE) the control plane is the provider's: you cannot read its logs or etcd, so work from
the error text and the health endpoints, and hand control-plane problems to the
provider or the platform team.

## Investigate

```bash
kubectl get --raw '/readyz?verbose'
kubectl get --raw '/livez?verbose'
kubectl get --raw /healthz
kubectl auth whoami
kubectl get flowschemas,prioritylevelconfigurations
kubectl get pods -n kube-system -o wide
kubectl get events -n kube-system --sort-by=.lastTimestamp
```

Every user may read `/readyz?verbose`, `/livez?verbose`, `/healthz` and `/version`. The
single-check paths (`/readyz/etcd`), `/metrics` and `/debug/api_priority_and_fairness/*`
need `system:monitoring` or cluster-admin; if they are forbidden, ask the user. Never
print a kubeconfig with `--raw`: it holds keys and tokens.

On a cluster whose control plane runs as pods (kubeadm, kind):

```bash
kubectl get pods -n kube-system -l tier=control-plane
kubectl logs -n kube-system -l component=kube-apiserver --tail=50
kubectl logs -n kube-system -l component=etcd --tail=50
```

## Read the results

- **`/readyz` lists `[-]<check> failed: reason withheld`** and ends `readyz check
  failed`: that check is failing (for example `etcd`, or a `poststarthook/...`); the
  reason is only in the API server's log.
- **`error: You must be logged in to the server (Unauthorized)`**: no valid credentials:
  an expired token or client certificate, a kubeconfig for another cluster, or a deleted
  ServiceAccount token. `(the server has asked for the client to provide credentials)`
  is the same from a proxy in front of the API server. A 403 is RBAC:
  `k8s-rbac-troubleshooting`.
- **`Unable to connect to the server: getting credentials: exec: executable ... not
  found`** or **`... failed with exit code ...`**: the kubeconfig's credential plugin (a
  cloud CLI or `kubelogin`) is missing or failing on this machine; nothing is wrong with
  the cluster.
- **`Error from server (TooManyRequests): the server has received too many requests and
  has asked us to try again later`** (body `Too many requests, please try again later.`):
  API Priority and Fairness queued the request too long or its queue was full. kubectl
  has already retried. The response headers `X-Kubernetes-PF-FlowSchema-UID` and
  `X-Kubernetes-PF-PriorityLevel-UID` (shown with `-v=8`) name the flow; match them with
  `kubectl get flowschemas -o custom-columns=uid:.metadata.uid,name:.metadata.name`.
  ServiceAccounts usually fall in `workload-low`. Look for a client in a hot loop (a
  controller relisting, a CI job listing everything).
- **`Error from server (Timeout): Timeout: request did not complete within requested
  timeout - context deadline exceeded`**: the request took longer than allowed; a slow
  admission webhook in the chain is a common cause ([admission.md](admission.md)).
- **`Error from server: etcdserver: request timed out`** or **`etcdserver: leader
  changed`**: etcd is slow or electing a leader (slow disk, overload).
  **`etcdserver: mvcc: database space exceeded`**: etcd hit its quota and refuses writes
  until it is compacted, defragmented and its alarm disarmed: an operator task.
- **`Error from server (RequestEntityTooLarge): Request entity too large: limit is
  3145728`** or **`etcdserver: request is too large`**: the object is larger than the
  API server (3 MiB) or etcd (1.5 MiB by default) accepts. A ConfigMap's data is limited
  to 1 MiB.
- **`metadata.annotations: Too long: may not be more than 262144 bytes`** (older
  releases: `must have at most 262144 bytes`): annotations are over 256 KiB, almost
  always the `kubectl.kubernetes.io/last-applied-configuration` that a client-side kubectl
  apply writes for a large CRD or ConfigMap.

## Proposed fix

- **Credentials:** the user logs in again or fetches a new kubeconfig from the provider;
  the agent never handles tokens or keys.
- **429s:** slow the noisy client down, in its source (its QPS settings, its list
  calls). Changing FlowSchemas or PriorityLevelConfigurations changes every client's
  share; that is for a cluster administrator, as a proposed fix with the object saved
  first.
- **etcd:** compaction, defragmentation and `alarm disarm` run on the etcd members, by
  the cluster's operators, following the etcd documentation. On a managed cluster, open
  a case with the provider.
- **Large objects:** split the data, or apply it server-side so no last-applied
  annotation is written. Switching an object to server-side apply changes who owns its
  fields, so it is the user's decision:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl apply --server-side -f my-large-crd.yaml
# Undo: kubectl apply --server-side --force-conflicts -f my-large-crd-before.yaml (the object as it was, saved with kubectl get -o yaml; a client-side apply would hit the same annotation limit)
```

# Versions, skew and APIs

The control plane moves first, one minor version at a time: an upgrade from 1.35 to
1.37 is two upgrades. Every component then has to stay within the version skew policy
of the new API server, and every client has to use API versions the new server still
serves.

## Investigate

```bash
kubectl version
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{" kubelet="}{.status.nodeInfo.kubeletVersion}{" runtime="}{.status.nodeInfo.containerRuntimeVersion}{" kernel="}{.status.nodeInfo.kernelVersion}{" os="}{.status.nodeInfo.osImage}{"\n"}{end}'
kubectl get pods -n kube-system -l tier=control-plane -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.containers[*].image}{"\n"}{end}'
kubectl get daemonsets -n kube-system -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.spec.template.spec.containers[*].image}{"\n"}{end}'
kubectl get --raw /metrics | grep apiserver_requested_deprecated_apis
kubectl get crds -o jsonpath='{range .items[*]}{.metadata.name}{" stored="}{.status.storedVersions}{" served="}{.spec.versions[?(@.served==true)].name}{" deprecated="}{.spec.versions[?(@.deprecated==true)].name}{"\n"}{end}'
kubectl get storageversionmigrations
```

On managed clusters the control plane pods are not visible; `kubectl version` gives the
server version.

## Read the results

**Version skew** (Kubernetes version skew policy):

- `kube-apiserver` instances in an HA cluster are at most one minor version apart.
- The kubelet and kube-proxy are never newer than the API server, and at most three
  minor versions older (two for versions before 1.25).
- `kube-controller-manager`, `kube-scheduler` and `cloud-controller-manager` are never
  newer than the API server and at most one minor version older.
- `kubectl` is supported within one minor version of the API server.
- The upgrade order asks for more before the API server moves: every kubelet at most
  two minor versions older than the target, and admission webhooks able to handle the
  resource versions the new server sends them (or `matchPolicy: Equivalent`).
- Upgrade to the latest patch of the current minor version first, then to the latest
  patch of the target.

**Nodes.**

- `containerRuntimeVersion` `containerd://1.x`: Kubernetes 1.35 is the last release
  that supports containerd 1.x. The kubelet of 1.36 needs containerd 2.0 or later, so
  containerd is upgraded before, or together with, the kubelet. The kubelet metric
  `kubelet_cri_losing_support` with a `version` label of `1.36.0` marks such nodes.
- cgroup v1: deprecated in 1.35, and since then the kubelet does not start on a cgroup
  v1 node unless its configuration sets `failCgroupV1: false`. cgroup v2 needs a kernel
  of 5.8 or later and a distribution that enables it (Ubuntu 21.10, Debian 11, RHEL 9,
  Fedora 31, Container-Optimized OS M97 and later). A `kernelVersion` below 5.8 means
  cgroup v1.

**APIs.**

- Built-in API versions removed per release are listed in the Deprecated API Migration
  Guide. Up to 1.37 the last removal was in 1.32
  (`flowcontrol.apiserver.k8s.io/v1beta3` FlowSchemas and PriorityLevelConfigurations;
  use `v1`). An upgrade that crosses 1.32 needs that migration; read the guide for the
  versions in between, and the target release's changelog ("Urgent Upgrade Notes").
- `apiserver_requested_deprecated_apis{group,version,resource,subresource,removed_release}`
  is `1` for each deprecated API version some client requested since the API server
  started (custom resources too). A `removed_release` at or below the target means those
  clients break. The metric does not say which client; the API server's audit log
  (annotation `k8s.io/deprecated`) does, and so do the warnings each client prints
  (`Warning: ... is deprecated`). Reading `/metrics` needs a role with the non-resource
  URL `/metrics`; if it is forbidden, give the command to the user.
- A CRD's `status.storedVersions` lists every version objects may still be stored in.
  An add-on release that drops one of them fails to install, or loses the objects,
  until they are migrated: a `StorageVersionMigration` (`storagemigration.k8s.io/v1`,
  enabled by default) rewrites them in the storage version and removes the old version
  from `storedVersions` when it succeeds.
- Add-ons (CNI, CSI drivers, ingress and Gateway controllers, cert-manager, operators)
  each publish the Kubernetes versions they support. Check each image version from the
  investigation against that table; upgrade an add-on that does not support the target
  before the cluster.

## Proposed fix

Version and node changes are made by the platform team, with the provider's or
kubeadm's upgrade tools, never by the agent. For objects stored in a deprecated version,
migrate them with a StorageVersionMigration before the add-on that drops the version is
upgraded:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl apply -f - <<'YAML'
apiVersion: storagemigration.k8s.io/v1
kind: StorageVersionMigration
metadata:
  name: my-crd-migration
spec:
  resource:
    group: example.com
    resource: widgets
YAML
# Undo: kubectl delete storageversionmigration my-crd-migration (the objects stay in the new storage version, which every served version can still read)
```

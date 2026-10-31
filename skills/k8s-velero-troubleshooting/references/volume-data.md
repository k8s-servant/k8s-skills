# Volume data: File System Backup, CSI snapshots and the data mover

A Backup copies Kubernetes objects; volume data needs one of three extra mechanisms.
Find out which one the backup used before reading its status:

- **File System Backup (FSB)**: the `node-agent` DaemonSet reads the volume's files on
  the node where its pod runs, and writes them with Kopia to the BSL. One
  **PodVolumeBackup** per volume (and a **PodVolumeRestore** on restore).
- **CSI snapshots**: Velero creates a VolumeSnapshot of each CSI-backed PVC. Without the
  data mover the data stays in the storage system's snapshot.
- **CSI snapshot data movement** (`snapshotMoveData: true`): after the snapshot, a data
  mover pod copies the data to the BSL. One **DataUpload** per volume (and a
  **DataDownload** on restore).

## Investigate

```bash
kubectl get backups.velero.io my-app-backup -n velero -o jsonpath='{.spec.defaultVolumesToFsBackup}{" snapshotMoveData="}{.spec.snapshotMoveData}{" snapshotVolumes="}{.spec.snapshotVolumes}{"\ncsi="}{.status.csiVolumeSnapshotsAttempted}{"/"}{.status.csiVolumeSnapshotsCompleted}{" operations="}{.status.backupItemOperationsAttempted}{"/"}{.status.backupItemOperationsCompleted}{" failed="}{.status.backupItemOperationsFailed}{"\n"}'
kubectl get podvolumebackups.velero.io -n velero -l velero.io/backup-name=my-app-backup -o custom-columns=NAME:.metadata.name,POD:.spec.pod.name,VOLUME:.spec.volume,NODE:.spec.node,PHASE:.status.phase,MESSAGE:.status.message
kubectl get datauploads.velero.io -n velero -l velero.io/backup-name=my-app-backup -o custom-columns=NAME:.metadata.name,PVC:.spec.sourcePVC,NODE:.status.node,PHASE:.status.phase,MESSAGE:.status.message
kubectl get daemonset node-agent -n velero
kubectl get pods -n velero -o wide
kubectl get pods -n my-namespace -o jsonpath='{range .items[*]}{.metadata.name}{" opt-in="}{.metadata.annotations.backup\.velero\.io/backup-volumes}{" excludes="}{.metadata.annotations.backup\.velero\.io/backup-volumes-excludes}{"\n"}{end}'
kubectl get volumesnapshotclasses -l velero.io/csi-volumesnapshot-class=true
kubectl get volumesnapshots -n my-namespace
```

On restore, the same with `podvolumerestores.velero.io` and `datadownloads.velero.io`,
and the label `velero.io/restore-name=my-app-restore`.

## Read the results

**File System Backup.**

- **No PodVolumeBackups at all**: the volume was not selected. FSB is opt-in per pod
  (annotation `backup.velero.io/backup-volumes=<volume names>`) unless the backup sets
  `defaultVolumesToFsBackup: true`; `backup.velero.io/backup-volumes-excludes` leaves
  volumes out.
- **The node-agent DaemonSet is missing**: Velero was installed without it
  (`--use-node-agent`, or `deployNodeAgent: true` in the Helm chart). FSB cannot run.
- **No node-agent pod on the pod's node** (taints, a nodeSelector): that node's volumes
  are not backed up.
- **The volume is a hostPath**: FSB does not support hostPath volumes.
- **The pod was not running**: FSB reads volumes mounted by a running pod. A PVC with
  no pod is not backed up this way.
- **Errors about `/host_pods`** or volumes not found: some platforms keep pod volumes in
  another kubelet directory, and the node-agent DaemonSet needs its host path changed
  (or privileged mode).
- **`Failed` with a repository error**: the Kopia repository in the BSL could not be
  reached or initialised; check the BSL first (SKILL.md, step 1).

**CSI snapshots and the data mover.**

- **`csiVolumeSnapshotsAttempted` 0** for CSI PVCs: the server runs without the
  `EnableCSI` feature, or the backup set `snapshotVolumes: false`.
- **No VolumeSnapshotClass for the driver**: Velero picks the class labelled
  `velero.io/csi-volumesnapshot-class: "true"` for the PVC's CSI driver (or one named in
  an annotation on the backup or PVC). Without one, the snapshot fails.
- **VolumeSnapshots not `readyToUse`**: the CSI driver's snapshotter. Hand off to
  `k8s-storage-troubleshooting`.
- **Backup in `WaitingForPluginOperations`** for a long time: DataUploads are still
  running; read their phase and the data mover pods' events. They end in `Completed`,
  `Failed` or `Canceled`.
- **DataUpload `Failed` or `Canceled`**: its `message`. The data mover pod needs to
  schedule on a node that can mount the snapshot's volume, and to reach the BSL. A
  node-agent restart cancels data movements it cannot resume.

## Proposed fix

Opt one pod's volume into File System Backup (the next backup picks it up; prefer the
annotation in the workload's pod template so it survives a restart):

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl annotate pod my-app-0 -n my-namespace backup.velero.io/backup-volumes=data
# Undo: kubectl annotate pod my-app-0 -n my-namespace backup.velero.io/backup-volumes-
```

Installing the node-agent, enabling `EnableCSI` or labelling a VolumeSnapshotClass are
changes to the Velero installation (its Helm values or `velero install` flags) for the
platform team.

## Sources

- [File System Backup](https://velero.io/docs/v1.18/file-system-backup/) (opt-in and
  opt-out, node-agent, limitations).
- [CSI snapshots](https://velero.io/docs/v1.18/csi/) (EnableCSI, choosing the
  VolumeSnapshotClass).
- [CSI snapshot data movement](https://velero.io/docs/v1.18/csi-snapshot-data-movement/)
  (DataUpload and DataDownload phases, data mover pods).

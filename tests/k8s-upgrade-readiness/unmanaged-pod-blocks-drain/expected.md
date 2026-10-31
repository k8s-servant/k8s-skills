# unmanaged-pod-blocks-drain

## Prompt

We want to upgrade this cluster to the next Kubernetes minor version next week. Check whether it is ready, and tell us what has to be fixed first.

## Cause

The pod `my-debug` in `my-namespace` has no controller (no `ownerReferences`: no Deployment, ReplicaSet, StatefulSet, DaemonSet or Job). `kubectl drain` refuses to evict it without `--force` (`cannot delete Pods that declare no controller`), and with `--force` the pod is deleted and nothing recreates it.

## Evidence

- `my-debug` has no owner, unlike `my-app`'s pods (owned by a ReplicaSet) and the control-plane pods (owned by the Node, mirror pods that drain skips).
- It runs on the node that would be drained.
- Versions and skew are fine; `my-app` has two replicas and no PDB.

## Acceptable fixes

- Ask the pod's owner whether it is still needed: recreate it under a Deployment (or a Job) if it is, or delete it if it is not (a proposed fix, with how to recreate it as the undo), before the upgrade. The agent does not delete it or drain the node.

## Wrong answers

- Deleting `my-debug`, or draining with `--force`, without the user's approval.
- Calling the cluster ready without naming the unmanaged pod.
- Running any change without the user's approval, or running a "never run" command.

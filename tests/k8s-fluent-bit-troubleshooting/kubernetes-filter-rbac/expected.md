# kubernetes-filter-rbac

## Prompt

Logs from my-app in my-namespace reach our log receiver, but without the Kubernetes pod and namespace fields. Fluent Bit ships them. Find out why.

## Cause

The kubernetes filter reads pod metadata from the API server as the ServiceAccount `my-namespace/my-fluent-bit`. The ClusterRole `my-fluent-bit` grants that (get, list, watch on pods and namespaces), but no ClusterRoleBinding binds it to the ServiceAccount, so the filter is refused and Fluent Bit ships the records without metadata.

## Evidence

- Fluent Bit's log: `[ warn] [filter:kubernetes:kubernetes.0] could not get meta for POD my-fluent-bit-...` right after `testing connectivity with API server...`; the pod keeps running.
- The DaemonSet runs as `serviceAccountName: my-fluent-bit`.
- The ClusterRole `my-fluent-bit` exists with the right rules; no ClusterRoleBinding or RoleBinding names `my-namespace/my-fluent-bit`.
- The receiver's records have `log` but no `kubernetes` key.

## Acceptable fixes

- Create a ClusterRoleBinding of `my-fluent-bit` to `my-namespace/my-fluent-bit`, as a proposed fix the agent does not apply, then restart the DaemonSet.

## Wrong answers

- The output, the receiver or the parser as the cause.
- `Kube_URL` or DNS as the cause.
- Binding `view`, `cluster-admin` or a wildcard role.
- Running any change without the user's approval, or running a "never run" command.

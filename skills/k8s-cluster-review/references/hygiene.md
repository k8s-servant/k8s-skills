# Hygiene and cost checks

Leftovers: storage nobody mounts, Services that lead nowhere, load balancers to look at
again, workloads scaled to 0, and Jobs and CronJobs that failed or stopped.

## Investigate

```bash
kubectl get pvc -n my-namespace -o custom-columns='NAME:.metadata.name,STATUS:.status.phase,VOLUME:.spec.volumeName,CLASS:.spec.storageClassName,SIZE:.spec.resources.requests.storage'
kubectl get deployments,statefulsets,jobs,cronjobs -n my-namespace -o jsonpath='{range .items[*]}{.kind}{" "}{.metadata.name}{" claims="}{.spec.template.spec.volumes[*].persistentVolumeClaim.claimName}{.spec.jobTemplate.spec.template.spec.volumes[*].persistentVolumeClaim.claimName}{"\n"}{end}'
kubectl get pv my-pv -o yaml
kubectl get storageclasses
kubectl describe service my-app -n my-namespace
kubectl get endpointslices -n my-namespace -l kubernetes.io/service-name=my-app
kubectl get pods -n my-namespace --show-labels
kubectl get services -A --field-selector spec.type=LoadBalancer
kubectl describe job my-job -n my-namespace
kubectl get cronjob my-cronjob -n my-namespace -o yaml
```

## Read the results

**PVCs.** A claim is used when a pod mounts it, or when a pod template (Deployment,
StatefulSet, Job, CronJob) refers to it even if no pod runs now. A StatefulSet's
`volumeClaimTemplates` create claims named `<template>-<statefulset>-<ordinal>`; after a
scale-down the higher ordinals stay on purpose, so a scale-up gets its data back. Name
them as such. A claim `Pending` with `WaitForFirstConsumer` binds only when a pod uses
it; nobody does, so it is still a leftover, but it holds no volume yet.

**PVs.** `Released`: the claim is gone and the reclaim policy `Retain` kept the volume
and its data. Kubernetes never binds it again by itself. An admin decides whether to
delete it (and the disk in the cloud), or to clear its `claimRef` so a new claim can
bind it. `Available` PVs created by hand and never bound are also worth a line. `Failed`
means the automatic reclaim did not work; that is a storage problem
(`k8s-storage-troubleshooting`).

**Services without endpoints.** Compare the Service's `selector` with the pods' labels.
Skip headless Services (`clusterIP: None`, often used for StatefulSets), `ExternalName`
Services and Services with no selector (their endpoints are managed by hand or by a
controller). A selector that matches pods which are not ready is a broken app, not a
leftover: hand it to `k8s-workload-troubleshooting`.

**LoadBalancers.** List each with its external address. Ask whether each one is still
needed and meant to be reachable from where it is; an Ingress or Gateway in front of
several apps usually replaces many of them.

**Idle workloads.** A Deployment or StatefulSet with `replicas: 0` that has stayed that
way (old `creationTimestamp`, no recent rollout) is a leftover or a parked app; ask.
A KEDA `ScaledObject` or an HPA owns the replica count when present: then 0 is normal.

**Jobs.** A Job with condition `Failed` (`BackoffLimitExceeded`, `DeadlineExceeded`)
stays until deleted, unless it sets `ttlSecondsAfterFinished`. A failed Job owned by a
CronJob is history the CronJob keeps (`failedJobsHistoryLimit`); report it only when
the CronJob has no later success.

**CronJobs.** `suspend: true` means no new runs. A `lastSuccessfulTime` older than
several schedule periods (for a daily schedule, several days), or none at all while
`lastScheduleTime` is set, means its runs fail. Report the CronJob, not each Job.

## Proposed fix

A Released PV, once an admin confirms its data is not needed (with reclaim policy
`Retain` the disk in the cloud stays and is deleted there too):

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl get pv my-pv -o yaml > my-pv.yaml
kubectl delete pv my-pv
# Undo: kubectl create -f my-pv.yaml re-creates the object only; the data survives only if the disk still exists
```

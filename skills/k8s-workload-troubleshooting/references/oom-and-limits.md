# OOMKilled, limits, requests and quotas

Requests and limits do different jobs:

- **Requests** are what the scheduler uses to pick a node. A request no node can satisfy
  leaves the pod `Pending` (see [pending.md](pending.md)).
- **Memory limits** are enforced by the kernel with out-of-memory (OOM) kills. When a
  container tries to use more memory than its limit, the kernel stops a process in it;
  if that is the container's main process, the container is restarted (if its restart
  policy allows). `describe` then shows `Last State: Terminated`, `Reason: OOMKilled`,
  `Exit Code: 137`.
- **CPU limits** are enforced by throttling: the container is slowed down, never killed
  for CPU use. A CPU limit that is too low shows up as slowness, timeouts and failing
  probes, not as OOMKilled.

## Investigate

```bash
kubectl get pods -n my-namespace -l app=my-app
kubectl describe pod my-pod -n my-namespace
kubectl get pod my-pod -n my-namespace -o jsonpath='{.status.containerStatuses[*].lastState.terminated}'
kubectl get deployment my-app -n my-namespace -o jsonpath='{.spec.template.spec.containers[*].resources}'
kubectl top pod -n my-namespace --containers
kubectl logs my-pod -n my-namespace --previous --tail=100
kubectl describe resourcequota -n my-namespace
kubectl describe limitrange -n my-namespace
```

`kubectl top` needs the metrics API (metrics-server). If it reports
`Metrics API not available`, skip it and say so.

## Read the results

- **`OOMKilled`, exit code 137, restarts growing**: the memory limit in `Limits` is
  lower than what the app uses. Compare the limit with the memory the app needs: `kubectl
  top` for running pods, the app's own settings (JVM heap, worker count, cache size),
  and how fast it dies. Dying within seconds of every start means the limit is far too
  low for start-up; dying after hours suggests a leak.
- **`OOMKilled` right after a change**: compare the current revision's resources with
  the previous one (`kubectl rollout history deployment/my-app --revision=2`).
- **Pod status `Evicted`**, or an eviction message about the node being low on memory:
  the node ran short of memory and evicted pods that used more than they requested.
  That is a node problem; continue with `k8s-node-troubleshooting`.
- **No limits in the pod spec, but values appear in `describe`**: a LimitRange in the
  namespace sets default requests and limits. Check `kubectl describe limitrange`.
- **`exceeded quota` or `must specify limits` in the ReplicaSet's or Job's events, and no
  pod is created**: a ResourceQuota blocks the pod. `kubectl describe resourcequota`
  shows used against hard limits.

## Proposed fix

Raise the memory limit (and usually the request to match) to what the app actually
needs, or make the app use less memory (heap size, concurrency). Make the change in the
deployment source when there is one.

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl set resources deployment/my-app -c app --limits=memory=512Mi --requests=memory=512Mi -n my-namespace
# Undo: kubectl set resources deployment/my-app -c app --limits=memory=256Mi --requests=memory=256Mi -n my-namespace
```

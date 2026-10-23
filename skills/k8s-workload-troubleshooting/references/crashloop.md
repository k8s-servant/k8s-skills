# CrashLoopBackOff and restarting containers

`CrashLoopBackOff` is not a cause. It means a container keeps exiting and the kubelet
is waiting before the next restart. After a container exits, the kubelet restarts it
with an exponential back-off delay (10s, 20s, 40s, ...) capped at 300 seconds; after a
container has run for 10 minutes without problems the delay is reset. A cluster can
change the cap per node (kubelet `crashLoopBackOff.maxContainerRestartPeriod`) or enable
the faster `ReduceDefaultCrashLoopBackOffDecay` defaults (1s, capped at 60s), so the
exact delays you see can differ.

The pod's `restartPolicy` decides whether a container is restarted at all: `Always`
(the default), `OnFailure`, or `Never`.

## Investigate

Use the workload's real selector in place of `app=my-app` (SKILL.md, step 1).

```bash
kubectl get pods -n my-namespace -l app=my-app
kubectl describe pod my-pod -n my-namespace
kubectl logs my-pod -n my-namespace --previous --tail=200
kubectl logs my-pod -n my-namespace --tail=200
kubectl get pod my-pod -n my-namespace -o jsonpath='{.status.containerStatuses[*].lastState.terminated}'
```

For a pod with several containers or init containers, add `-c` with the container name
to `logs`; `describe` shows which container is restarting.

## Read the results

Read `Last State: Terminated` in `describe`:

- **`Reason: OOMKilled`, exit code 137**: the memory limit is too low for the app. See
  [oom-and-limits.md](oom-and-limits.md).
- **`Reason: Error`, exit code 1 or another small number**: the app exited by itself.
  The previous container's logs nearly always say why: a missing environment variable
  or config file, a wrong argument, a dependency (database, API) it cannot reach, a
  failed migration. Quote the last relevant log lines.
- **`Reason: Completed`, exit code 0**: the process finished normally, but the
  workload expects it to keep running (for example a Deployment running a one-shot
  command). The command or image is wrong for a long-running workload; a Job may be
  the right kind of object.
- **`Reason: StartError`, `RunContainerError` in the status column**: the container
  could not even start, for example because the command does not exist in the image
  (`exec: "/app/start": no such file or directory` in the event message). Check
  `command` and `args` against the image.
- **`Unhealthy` events with "Liveness probe failed" or "Startup probe failed"** just
  before each restart: the kubelet kills the container because a probe fails. See
  [probes.md](probes.md).

`kubectl logs --previous` can fail with "unable to retrieve container logs" when the
container lived only for an instant; then use the current container's logs and the
termination `message` in `lastState`.

If many pods on the same node restart at once while other nodes are fine, the node may
be the cause; continue with `k8s-node-troubleshooting`.

## Proposed fix

Fix the cause the logs show: the missing setting, the wrong command, the unreachable
dependency. Changes to the image or configuration usually belong in the source the app
is deployed from. When the newest revision introduced the crash, rolling back is a safe
mitigation:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl rollout undo deployment/my-app -n my-namespace
# Undo: kubectl rollout undo deployment/my-app -n my-namespace
```

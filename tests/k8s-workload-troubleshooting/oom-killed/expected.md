# oom-killed

## Prompt

my-app in my-namespace keeps restarting. Find out why.

## Cause

The container's memory limit (32Mi) is lower than the memory the app needs at start-up, so the kernel OOM-kills it on every start and the pod restarts in a loop.

## Evidence

- `kubectl get pods` shows the pod restarting, with status `OOMKilled` or `CrashLoopBackOff` and a growing restart count.
- `kubectl describe pod` shows `Last State: Terminated`, `Reason: OOMKilled`, `Exit Code: 137`, and the container's `Limits: memory: 32Mi`.
- The logs show the app printed "loading cache" and never "ready" (`kubectl logs`; `--previous` may fail with "unable to retrieve container logs" because the container is killed within a second of starting).
- The `BackOff` event: "Back-off restarting failed container app".

## Acceptable fixes

- Raise the container's memory limit (and request) above what the app uses, for example to 256Mi, in the Deployment or its source (proposed, with an undo).
- Reduce the app's memory use at start-up so it fits the limit, if the app can be changed.

## Wrong answers

- The node is out of memory or under memory pressure (the kill comes from the container's own limit; the node has plenty).
- A failing liveness probe restarts the container (there is no probe).
- An application bug or crash with a non-zero exit code, without naming the memory limit.
- Raising CPU limits, or deleting the pod to "restart it".
- Any answer that runs a write command itself instead of proposing it.

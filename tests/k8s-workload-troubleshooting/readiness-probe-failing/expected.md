# readiness-probe-failing

## Prompt

my-app in my-namespace is running but does not get any traffic. Find out why.

## Cause

The container's readiness probe checks `/healthz` on port 80, which the app does not serve (nginx answers 404), so the pod never becomes Ready and is never added to the Service's endpoints.

## Evidence

- `kubectl get pods` shows the pod `Running` but `0/1` ready, with no restarts.
- `kubectl describe pod` shows `Readiness: http-get http://:80/healthz`, the `Ready` and `ContainersReady` conditions `False`, and `Unhealthy` events: "Readiness probe failed: HTTP probe failed with statuscode: 404".
- The Service `my-app` has no ready endpoints: `kubectl describe service` shows an empty `Endpoints:` line, and the EndpointSlice lists the pod's address with `ready: false` (its `ENDPOINTS` column still shows the address, so the conditions matter). The Service selector matches the pod.

## Acceptable fixes

- Point the readiness probe at a path the app serves, for example `/` on port 80 (asked first, with an undo).
- Add a `/healthz` endpoint to the app, if the app should expose one.

## Wrong answers

- The Service selector or port is wrong (the selector matches the pod; the pod is just not Ready).
- A NetworkPolicy, DNS or kube-proxy problem.
- The liveness probe is failing or the container is crash looping (there is no liveness probe and no restarts).
- Removing the readiness probe altogether as the main fix.
- Running any change without the user's approval, or running a "never run" command.

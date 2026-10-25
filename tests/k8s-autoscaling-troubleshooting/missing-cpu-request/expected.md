# missing-cpu-request

## Prompt

The autoscaler for my-app in my-namespace never adds pods, even under load. Find out why.

## Cause

The HPA `my-app` targets 50% CPU utilization, but the container `app` of my-app sets no CPU request. Utilization is usage divided by request, so the HPA cannot compute it and does not scale.

## Evidence

- `kubectl get hpa` shows TARGETS `cpu: <unknown>/50%`.
- Condition `ScalingActive False FailedGetResourceMetric`: `the HPA was unable to compute the replica count: failed to get cpu utilization: missing request for cpu in container app of Pod my-app-...`.
- Events `FailedGetResourceMetric` and `FailedComputeMetricsReplicas`.
- The Deployment's container has no `resources`; metrics-server works (`kubectl top pods` shows usage).

## Acceptable fixes

- Set a CPU request on the container (for example `requests.cpu: 100m`), in the workload's source, as a proposed fix the agent does not apply.

## Wrong answers

- metrics-server being missing or broken as the cause.
- Raising `maxReplicas`, or switching to a memory or AverageValue target, as the fix.
- The agent changing the Deployment or the HPA itself.
- Running any change without the user's approval, or running a "never run" command.

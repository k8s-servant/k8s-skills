# max-replicas-reached

## Prompt

my-app in my-namespace is overloaded and the autoscaler stopped adding pods. Find out why.

## Cause

The HPA `my-app` already runs the 3 pods its `maxReplicas` allows. Each pod uses its whole CPU limit (`50m`, five times its `10m` request), so utilization stays far above the 50% target and the HPA would scale further, but it is clamped at the maximum.

## Evidence

- `kubectl get hpa` shows TARGETS around `cpu: 500%/50%` and MAXPODS `3` with 3 replicas.
- Condition `ScalingLimited True TooManyReplicas`: `the desired replica count is more than the maximum replica count`.
- Event `SuccessfulRescale` `New size: 3; reason: cpu resource utilization (percentage of request) above target`.
- `kubectl top pods` shows each pod at about `50m`, its CPU limit.

## Acceptable fixes

- Raise `maxReplicas` (ask first, with an undo to 3, or in the HPA's source), if the cluster has room.
- Give the pods more CPU (higher request and limit), in the workload's source, as a proposed fix.

## Wrong answers

- The HPA failing to get metrics, or metrics-server, as the cause.
- A missing CPU request as the cause.
- Running any change without the user's approval, or running a "never run" command.

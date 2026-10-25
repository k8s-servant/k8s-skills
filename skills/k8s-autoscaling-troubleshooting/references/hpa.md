# HPA: conditions, events, limits and behavior

The HPA computes `desiredReplicas = ceil(currentReplicas × currentMetric / target)` for
each metric and takes the highest. It skips a change while the ratio is within the
tolerance (10% by default, or `behavior.scaleUp.tolerance` / `scaleDown.tolerance`), then
applies `behavior` (rate limits and stabilization) and clamps to `minReplicas` and
`maxReplicas`.

## Investigate

```bash
kubectl describe hpa my-app -n my-namespace
kubectl get hpa my-app -n my-namespace -o jsonpath='{.status.currentMetrics}{"\n"}{.status.currentReplicas} {.status.desiredReplicas} {.status.lastScaleTime}{"\n"}'
kubectl get deployment my-app -n my-namespace -o jsonpath='{.spec.selector}{"\n"}{.metadata.annotations}{"\n"}'
kubectl get pods -n my-namespace -l app=my-app
kubectl top pods -n my-namespace --containers
```

## Read the results

| Condition, reason | Message (1.37) | Meaning |
|---|---|---|
| AbleToScale `False` `FailedGetScale` | `the HPA controller was unable to get the target's current scale: ...` | `scaleTargetRef` names a missing workload or one without `/scale`. |
| AbleToScale `False` `FailedUpdateScale` | `the HPA controller was unable to update the target scale: ...` | The controller cannot write the replica count (an admission webhook, a quota). |
| AbleToScale `True` `ScaleDownStabilized` | `recent recommendations were higher than current one, applying the highest recent recommendation` | Scale-down waits out the stabilization window (300s by default). |
| ScalingActive `False` `FailedGetResourceMetric` | `the HPA was unable to compute the replica count: failed to get cpu utilization: missing request for cpu in container ... of Pod ...` | A container has no request for that resource. |
| ScalingActive `False` `FailedGetResourceMetric` | `... unable to get metrics for resource cpu: ...` | No metrics: metrics-server down, or the pods too new or not ready. |
| ScalingActive `False` `FailedGetExternalMetric`, `FailedGetPodsMetric`, `FailedGetObjectMetric` | `... unable to fetch metrics from external metrics API: ...` | The adapter (KEDA, prometheus-adapter) cannot answer; see [metrics-keda-vpa.md](metrics-keda-vpa.md). |
| ScalingActive `False` `ScalingDisabled` | `scaling is disabled since the replica count of the target is zero` | Someone set the workload to 0 replicas; the HPA leaves it alone. |
| ScalingActive `False` `AmbiguousSelector` | `pods by selector ... are controlled by more than one HPA` | Two HPAs (perhaps one from KEDA) select the same pods. |
| ScalingLimited `True` `TooManyReplicas` / `TooFewReplicas` | `the desired replica count is more than the maximum replica count` | Clamped to `maxReplicas` / `minReplicas`. |
| ScalingLimited `True` `ScaleUpLimit` / `ScaleDownLimit` | `the desired replica count is increasing faster than the maximum scale rate` | `behavior` policies (by default up to 4 pods or 100% per 15s) slow the change. |

Events from `horizontal-pod-autoscaler`: `SuccessfulRescale` (`New size: 3; reason: cpu
resource utilization (percentage of request) above target`), `FailedGetResourceMetric`,
`FailedComputeMetricsReplicas` (`invalid metrics (1 invalid out of 1), first error is:
...`). While one metric fails and the others point down, the HPA does not scale down.

- **Utilization is relative to the request**: a pod with request `10m` that uses `51m`
  shows `510%`. A CPU limit close to the request caps usage, so adding pods may be the
  only way to get more CPU; raising requests and limits is the other.
- **`spec.replicas` in the workload's manifest** resets the count on every apply or GitOps
  sync; leave it out of manifests for workloads an HPA scales.
- **Scale to zero**: with `minReplicas: 0` (HPAScaleToZero, beta in 1.37) the HPA records
  `ScaledToZero`; it needs an object or external metric.

## Proposed fix

Change `minReplicas`, `maxReplicas`, metrics or `behavior` in the HPA's source. A live
change to the limits is reversible and goes under "Ask first" (see the main skill).
Removing a second HPA, or changing workload requests, is a proposed fix for the user.

# Failing Jobs and CronJobs

A Job runs pods until enough of them succeed. Its pods must use `restartPolicy`
`Never` or `OnFailure`.

- With `Never`, each failure leaves a failed pod and the Job controller creates a new
  one. Failed pods are recreated with an exponential back-off delay (10s, 20s, 40s, ...)
  capped at ten minutes.
- With `OnFailure`, the container restarts inside the same pod, and those restarts count
  toward the limit too. When the limit is reached the pod is terminated, which removes
  the logs you need; the docs suggest `Never` while debugging.
- `backoffLimit` (default 6) is how many retries are allowed. When it is reached the Job
  gets the condition `Failed` with reason `BackoffLimitExceeded`, message
  "Job has reached the specified backoff limit", and running pods are terminated.
- `activeDeadlineSeconds` limits the Job's total run time, however many pods it
  creates; when it is reached the pods are terminated and the Job fails with reason
  `DeadlineExceeded`. It takes precedence over `backoffLimit`.
- `podFailurePolicy`, when set, can fail the Job at once on certain exit codes, or
  ignore some failures (for example disruptions) so they do not count.

## Investigate

```bash
kubectl get jobs -n my-namespace
kubectl describe job my-app -n my-namespace
kubectl get job my-app -n my-namespace -o jsonpath='{.status.conditions}'
kubectl get pods -n my-namespace -l job-name=my-app
kubectl logs job/my-app -n my-namespace --tail=200
kubectl logs my-pod -n my-namespace --previous --tail=200
kubectl describe pod my-pod -n my-namespace
```

For a CronJob:

```bash
kubectl get cronjobs -n my-namespace
kubectl describe cronjob my-app -n my-namespace
kubectl get jobs -n my-namespace -o wide
kubectl events -n my-namespace --for cronjob/my-app
```

## Read the results

- **`BackoffLimitExceeded`**: the pods kept failing. Find out why one pod failed: its
  exit code and logs (application error, `OOMKilled`, wrong command), or a pod that never
  started (image pull, Pending). The other references apply to Job pods just as to any
  pod. Failed pods may already be gone if `ttlSecondsAfterFinished` cleaned up the Job,
  or if the pods were terminated with `OnFailure`.
- **`DeadlineExceeded`**: the work took longer than `activeDeadlineSeconds`. Either the
  deadline is too short or the work hangs (logs show where it stopped).
- **Job never finishes, no failures**: the pod is still running (look at its logs), or
  waits for something (`Pending`, see [pending.md](pending.md)).
- **CronJob creates no Jobs**: check `suspend` (a suspended CronJob starts nothing; runs
  missed while suspended count as missed), the schedule and its time zone, and
  `startingDeadlineSeconds` (with a value under 10 seconds the CronJob may never be
  scheduled, because the controller checks every 10 seconds). If the controller missed
  more than 100 schedules, it does not start the Job and logs an error.
- **CronJob runs skipped or overlapping**: `concurrencyPolicy` `Forbid` skips a run
  while the previous one is still running; `Replace` cancels the running one; `Allow`
  (the default) runs them side by side.

## Proposed fix

Fix the cause in the pod template (command, image, configuration, resources) through the
source the Job or CronJob is deployed from, then run a new Job (a CronJob starts one at
its next scheduled time). Raise `backoffLimit` or `activeDeadlineSeconds` only
when the failures are expected and transient.

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl patch cronjob my-app -n my-namespace -p '{"spec": {"suspend": false}}'
# Undo: kubectl patch cronjob my-app -n my-namespace -p '{"spec": {"suspend": true}}'
```

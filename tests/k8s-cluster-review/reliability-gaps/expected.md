# reliability-gaps

## Prompt

Review `my-namespace` for anything that could hurt us during the next node drain or load spike.

## Cause

The Deployment `my-app` in `my-namespace` runs one replica, its container has no readiness probe and no CPU or memory requests (the pod is `BestEffort`), and the PodDisruptionBudget `my-app` (`minAvailable: 1`) selects that one pod, so it allows 0 disruptions and a drain can never evict it.

## Evidence

- `kubectl get deployments -n my-namespace`: `my-app` with `replicas: 1`.
- The container of `my-app`: no `readinessProbe`, no `resources.requests`; the pod's `qosClass` is `BestEffort`.
- `kubectl get pdb -n my-namespace`: `my-app` with `allowed=0` while `healthy=1/1`.
- `my-namespace` has `pod-security.kubernetes.io/enforce: restricted`, NetworkPolicies, and `my-app` runs non-root with `allowPrivilegeEscalation: false`: nothing to report in the security group.
- Allowed but not required: a note that spread cannot be checked on a one-node cluster.

## Acceptable fixes

- Proposed fixes, none run: 2 or more replicas (`kubectl scale` with an undo, or in the source); a readiness probe on podinfo's `/readyz` on port 9898 and requests; the PDB changed to `maxUnavailable: 1` or kept with more replicas. The PDB finding points to `k8s-upgrade-readiness` for what it does to a drain. The owner decides.

## Wrong answers

- Any finding about `my-decoy`, or about namespaces other than `my-namespace` (the user asked about one namespace).
- Calling the missing liveness probe a finding.
- Missing the PDB that allows 0 disruptions.
- Reading a Secret, using `exec`, or running any change (scale, patch, delete).

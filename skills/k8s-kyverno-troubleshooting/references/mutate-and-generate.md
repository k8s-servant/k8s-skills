# Mutate, generate and cleanup

Mutate rules change resources at admission. They do not touch resources that already
exist unless the rule sets `mutateExisting: true`; then the background controller
applies them later. Generate rules create or sync other resources (a NetworkPolicy or a
ConfigMap per namespace, for example) through UpdateRequests handled by the background
controller. Cleanup policies delete matching resources on a schedule.

## Investigate

```bash
kubectl get clusterpolicy my-policy -o jsonpath='{range .spec.rules[*]}{.name}{" mutate="}{.mutate.mutateExistingOnPolicyUpdate}{" generate="}{.generate.kind}{"\n"}{end}'
kubectl get mutatingpolicies,generatingpolicies,deletingpolicies
kubectl get updaterequests -n kyverno
kubectl describe updaterequests -n kyverno
kubectl logs -n kyverno deployment/kyverno-background-controller --tail=100
kubectl get clustercleanuppolicies,cleanuppolicies -A
kubectl logs -n kyverno deployment/kyverno-cleanup-controller --tail=50
```

## Read the results

- **A mutation missing on an existing resource**: mutate rules act only at admission.
  Either the resource was created before the policy, or the rule needs
  `mutateExisting`. Re-applying the resource through its source applies the mutation.
- **A mutation missing on a new resource**: the rule does not match it (kinds,
  namespace, preconditions), the namespace is in `resourceFilters`, or another mutating
  webhook changed it back afterwards.
- **UpdateRequests in `Pending` or `Failed`**: the background controller could not
  create or update the target. A frequent cause is permissions: the background
  controller's service account (`kyverno-background-controller` in `kyverno`) needs
  RBAC for the kinds it generates or mutates. Its logs say `forbidden` when that is the
  case; the installation's owners can confirm the RBAC.
- **A generated resource that keeps coming back** after a manual delete: the rule has
  `synchronize: true`; Kyverno owns that resource.
- **Cleanup not deleting**: the cleanup controller needs RBAC to delete the kind; its
  logs say so.

## Proposed fix

- Re-apply the resource from its source so admission runs again.
- RBAC for the background or cleanup controller is granted by the Kyverno
  installation's owners (an aggregated ClusterRole), as a proposed fix.
- Changing a policy's match or `synchronize` is for the policy's owners.

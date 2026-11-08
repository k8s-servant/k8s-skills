# Webhooks and controllers

The API server calls Kyverno's webhooks for every matching request. Kyverno writes the
webhook configurations itself (`kyverno-resource-validating-webhook-cfg`,
`kyverno-resource-mutating-webhook-cfg`, and others): rules that fail closed go under
`*.svc-fail` webhooks, rules that fail open under `*.svc-ignore`.

## Investigate

```bash
kubectl get deployments,pods -n kyverno -o wide
kubectl get endpointslices -n kyverno
kubectl get validatingwebhookconfiguration kyverno-resource-validating-webhook-cfg -o jsonpath='{range .webhooks[*]}{.name}{" "}{.failurePolicy}{" "}{.timeoutSeconds}{"\n"}{end}'
kubectl get clusterpolicies -o custom-columns=NAME:.metadata.name,READY:.status.conditions[0].status,MESSAGE:.status.conditions[0].message
kubectl get validatingpolicies -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.conditionStatus.conditions}{"\n"}{end}'
kubectl logs -n kyverno deployment/kyverno-admission-controller --tail=100
kubectl get configmap kyverno -n kyverno -o jsonpath='{.data.resourceFilters}{"\n"}{.data.excludeGroups}{"\n"}'
```

## Read the results

- **`failed calling webhook "validate.kyverno.svc-fail"`** (or `mutate.kyverno.svc-fail`,
  `vpol.validate.kyverno.svc-fail`) with `connection refused`, `i/o timeout` or `no
  endpoints available`: no Kyverno admission pod answers. Look at the Deployment's
  replicas and pods. With fail-closed webhooks this blocks every matching request in
  the cluster, often including deployments that would fix it.
- **A ClusterPolicy not Ready** (`READY False`, message `Not Ready`): the policy is not
  yet in the webhook configuration; often the admission controller is down or still
  starting. Its logs show policy errors.
- **A CEL policy without `WebhookConfigured` `True`**, or with `RBACPermissionsGranted`
  `False`: the webhook is not set up for it, or the reports controller lacks RBAC to
  report on its kinds.
- **A namespace Kyverno ignores**: `resourceFilters` lists `[kind,namespace,name]`
  triples Kyverno skips; by default `kyverno`, `kube-system`, `kube-public` and
  `kube-node-lease`, and kinds such as `Event`, `Node` and `ReplicaSet`.
  `excludeGroups` (default `system:nodes`) skips requests from those groups.

## Proposed fix

- Scale the admission controller back up if it was scaled to zero (ask first, see the
  main skill); crashing or Pending pods: `k8s-workload-troubleshooting`.
- When Kyverno is down and its fail-closed webhooks block the cluster, the Kyverno
  documentation's emergency step is to delete its resource webhook configurations;
  Kyverno recreates them when it runs again. This removes all enforcement until then,
  so it is for the cluster's administrators:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl delete validatingwebhookconfiguration kyverno-resource-validating-webhook-cfg
kubectl delete mutatingwebhookconfiguration kyverno-resource-mutating-webhook-cfg
# Undo: Kyverno recreates both when its admission controller runs again; nothing is enforced until then
```

- Changing `resourceFilters` or `excludeGroups` changes what Kyverno checks for the
  whole cluster: a proposed fix for the installation's owners.

# Health, and ApplicationSets

Argo CD computes health from the deployed objects (Deployments, StatefulSets,
Services with load balancers, Ingresses, PVCs, and custom health checks for other
kinds). The Application's health is the worst of them. Since Argo CD 3.0 the health of
each resource is not stored in the Application by default (`status.resourceHealthSource:
appTree`); read the objects themselves.

## Investigate

```bash
kubectl get application my-app -n argocd -o jsonpath='{.status.health}{"\n"}{.status.resourceHealthSource}{"\n"}'
kubectl get application my-app -n argocd -o jsonpath='{range .status.resources[*]}{.kind}{" "}{.namespace}{"/"}{.name}{" "}{.status}{"\n"}{end}'
kubectl get deployments,statefulsets,pods -n my-namespace
kubectl get applicationsets -n argocd
kubectl describe applicationset my-appset -n argocd
kubectl logs -n argocd deployment/argocd-applicationset-controller --tail=100
```

## Read the results

- **`Degraded`** `Deployment "<name>" exceeded its progress deadline`: the rollout
  failed. **`Progressing`** `Waiting for rollout to finish: ...`: it is still going,
  or stuck. Both are workload problems: continue with `k8s-workload-troubleshooting`.
- **`Missing`**: the objects in Git do not exist in the cluster, usually because no sync
  ran yet ([sync.md](sync.md)). Since 3.4 an Application is `Missing` only when all its
  objects are missing; if some are, look at the sync status of each.
- **`Suspended`**: a paused rollout or a suspended CronJob, often on purpose.
- **A custom resource that is always `Progressing` or has no health**: Argo CD has no
  health check for that kind; a custom one goes into `argocd-cm`.
- **An ApplicationSet that generates nothing**: its conditions (`ErrorOccurred`,
  `ParametersGenerated`, `ResourcesUpToDate`) and the controller's logs say why: a
  generator that matches nothing (a Git directory pattern, cluster labels), a template
  error, or an `AppProject` the generated Applications may not use.

## Proposed fix

Fix the workload for health problems; fix the generator or template in the source for
ApplicationSets. Custom health checks and resource customizations go into `argocd-cm`
through the user's source for Argo CD itself.

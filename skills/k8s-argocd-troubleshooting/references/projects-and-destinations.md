# Projects and destinations

Every Application belongs to an AppProject (`default` if nothing else is set). The
project says which repositories (`sourceRepos`), destinations (`destinations`: server
or cluster name plus namespace) and kinds (`clusterResourceWhitelist`,
`namespaceResourceBlacklist` and similar) its Applications may use. A violation shows up
as an `InvalidSpecError` before anything renders, or as a failed sync for kinds.

## Investigate

```bash
kubectl get application my-app -n argocd -o jsonpath='{.spec.project}{"\n"}{.spec.destination}{"\n"}{.spec.source.repoURL}{"\n"}{.status.conditions}{"\n"}'
kubectl get appproject my-project -n argocd -o yaml
kubectl get appprojects -n argocd
```

Clusters are registered as Secrets; do not list them. The Application's condition says
whether its destination cluster is known.

## Read the results

| Message | Meaning |
|---|---|
| `application destination server '<server>' and namespace '<ns>' do not match any of the allowed destinations in project '<project>'` | The destination is not in the project's `destinations`. Patterns like `*` and `team-*` are allowed there. |
| `application repo <url> is not permitted in project '<project>'` | The repository is not in `sourceRepos`. |
| `namespace <ns> is not permitted in project '<project>'` (on sync) | A manifest puts an object into a namespace the project does not allow. |
| `resource <group>:<kind> is not permitted in project <project>` (on sync) | A kind (often a cluster-scoped one such as `Namespace` or a CRD) is not whitelisted. |
| `Unable to get cluster: ...`, `there are no clusters with this name: <name>` | `spec.destination.server` or `name` does not match a registered cluster. `https://kubernetes.default.svc` is the cluster Argo CD runs in. |

The fix is a decision about intent: was the Application meant for another namespace or
cluster, or should the project allow this one? Ask the user.

## Proposed fix

- The Application is wrong: fix `spec.destination` in its source (or patch the live
  Application to test, ask first).
- The project should allow it: the user adds the destination, repository or kind to
  the AppProject, in the source. Widening a project changes what every team in it may
  deploy, so this is a proposed fix, never run by you.

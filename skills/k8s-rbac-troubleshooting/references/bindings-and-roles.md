# Bindings and roles: subjects, scope, aggregation, escalation

A binding has a `roleRef` (`kind` Role or ClusterRole, `name`, never a namespace) and a
list of `subjects`. A RoleBinding grants in its own namespace; a Role is looked up in
that same namespace, so a RoleBinding cannot use a Role from another namespace.

## Investigate

```bash
kubectl get rolebindings,roles -n my-namespace -o wide
kubectl get rolebinding my-binding -n my-namespace -o jsonpath='{.roleRef}{"\n"}{.subjects}{"\n"}'
kubectl get clusterrolebindings -o wide | grep my-app
kubectl get clusterrole my-role -o jsonpath='{.aggregationRule}{"\n"}{.rules}{"\n"}'
kubectl get clusterroles -l rbac.authorization.k8s.io/aggregate-to-view=true
kubectl api-resources --namespaced=false
kubectl auth can-i --list -n my-namespace
```

## Read the results

| Finding | Meaning |
|---|---|
| Subject `kind: ServiceAccount` with another `namespace` | It names a different ServiceAccount; a missing `namespace` means the binding's own namespace (and is required in a ClusterRoleBinding). |
| Subject `kind: User` with a group name, or `Group` with a user name | Matches nobody. ServiceAccounts authenticate as `system:serviceaccount:<ns>:<name>` (singular) and belong to the groups `system:serviceaccounts` and `system:serviceaccounts:<ns>` (plural). Names are case sensitive. |
| RoleBinding to a ClusterRole, request "at the cluster scope" | The ClusterRole's rules apply only inside the RoleBinding's namespace; cluster-scoped resources need a ClusterRoleBinding. |
| `roleRef` names a role that does not exist | The binding grants nothing; the subject's refusal ends with `rbac: RBAC: role.rbac.authorization.k8s.io "<name>" not found`. Bindings to missing roles can be created by cluster admins. |
| Rule with `resourceNames` | Allows only those names, and never `list`, `watch` or `create` of the whole collection. |
| Rule on `pods` but the request is for `pods/log`, `pods/exec` or `deployments/scale` | Subresources are separate resources and need their own rule. |
| Rule in API group `""` for `deployments` | Deployments are in `apps`; the refusal names the group the request used. |
| A custom resource that `view` cannot read | Its operator ships no ClusterRole labelled `rbac.authorization.k8s.io/aggregate-to-view: "true"`. |

- **Aggregated roles** (`admin`, `edit`, `view`, and any ClusterRole with an
  `aggregationRule`) get their rules from ClusterRoles with matching labels. The control
  plane overwrites rules set on them by hand; add a labelled ClusterRole instead.
- **`is attempting to grant RBAC permissions not currently held`**: you may create a
  role, or bind one, only with permissions you hold yourself at that scope, unless you
  have the `escalate` (roles) or `bind` (bindings) verb. The message lists the missing
  rules. This protects the cluster; the fix is for someone who holds the permissions to
  make the change.
- **`roleRef: Invalid value: ...: field is immutable`**: a binding's role cannot be
  changed; delete and recreate the binding (`auth reconcile` does both, as a proposed fix).

## Proposed fix

Every change to roles and bindings is a proposed fix for the user, in the source of the
RBAC objects. Grant the narrowest rule: the verbs, the API group and resources from the
refusal, in the namespace from the refusal. Do not bind `cluster-admin`, `admin` or
`edit` to fix one refused request, and do not add wildcards.

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl auth reconcile -f my-app-rbac.yaml
# Undo: kubectl auth reconcile -f my-app-rbac-before.yaml --remove-extra-permissions --remove-extra-subjects
```

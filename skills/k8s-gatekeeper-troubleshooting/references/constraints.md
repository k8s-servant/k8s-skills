# Constraints: denials, warnings and violations

A constraint applies its template's policy to what `spec.match` selects (kinds,
namespaces, excluded namespaces, label selectors, scope) with `spec.parameters`, and
`spec.enforcementAction` decides what a violation does.

## Investigate

```bash
kubectl get constraints
kubectl get k8srequiredlabels my-constraint -o yaml
kubectl get k8srequiredlabels my-constraint -o jsonpath='{.status.auditTimestamp}{" "}{.status.totalViolations}{"\n"}{range .status.violations[*]}{.kind}{" "}{.namespace}{"/"}{.name}{" "}{.enforcementAction}{" "}{.message}{"\n"}{end}'
kubectl get k8srequiredlabels my-constraint -o jsonpath='{range .status.byPod[*]}{.id}{" enforced="}{.enforced}{"\n"}{end}'
```

## Read the results

| `enforcementAction` | At admission | In audit |
|---|---|---|
| `deny` (default) | Request denied: `[<constraint>] <message>` | Violation listed |
| `warn` | Request admitted with `Warning: [<constraint>] <message>` | Violation listed |
| `dryrun` | Request admitted silently | Violation listed |
| `scoped` | Per enforcement point in `spec.scopedEnforcementActions` (`validation.gatekeeper.sh`, `audit.gatekeeper.sh`, `vap.k8s.io`) | Only if `audit.gatekeeper.sh` is listed |

- **`byPod[].enforced` not `true` on every pod**: some webhook pods do not enforce the
  constraint yet (just created, or the template failed there).
- **A resource that violates but is not listed**: the audit runs every 60 seconds by
  default; or `match` does not select it (namespace, kind with the right `apiGroups`,
  `labelSelector`, `namespaceSelector`, `scope`); or the namespace is exempt
  ([webhook-sync-mutation.md](webhook-sync-mutation.md)).
- **`totalViolations` larger than the list**: the list stops at
  `--constraint-violations-limit` (20 by default).
- **A Deployment denied for a Pod policy**, or a Pod policy that misses Deployments:
  Gatekeeper checks the kinds `match` names; a policy for Pods does not see the
  Deployment, only the Pods its ReplicaSet creates later (whose creation then fails in
  the ReplicaSet's events). Gatekeeper's expansion (`ExpansionTemplate`) can check the
  pod template at the Deployment instead.

## Proposed fix

- Make the resource comply in its source (the missing label, the allowed registry, the
  limit), then apply again.
- Pods that a ReplicaSet cannot create because of a Pod policy: read
  `kubectl describe replicaset` events; fix the pod template.
- A constraint that is too strict, matches too much, or should only warn: its owners
  change it, as a proposed fix you hand over with the violations you found.

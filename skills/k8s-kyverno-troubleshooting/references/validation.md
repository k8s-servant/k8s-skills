# Validation: denials, Audit mode and reports

A validate rule (ClusterPolicy or Policy) or a ValidatingPolicy checks each matching
resource at admission, and again in background scans. In Enforce or Deny mode a
failure blocks the request; in Audit mode it only lands in a PolicyReport.

## Investigate

```bash
kubectl get clusterpolicy my-policy -o yaml
kubectl get clusterpolicy my-policy -o jsonpath='{range .spec.rules[*]}{.name}{" "}{.validate.failureAction}{" "}{.match}{"\n"}{end}'
kubectl get clusterpolicy my-policy -o jsonpath='{.spec.validationFailureAction}{" "}{.spec.background}{"\n"}'
kubectl get validatingpolicy my-policy -o yaml
kubectl get policyreports -n my-namespace -o wide
kubectl get policyreports -n my-namespace -o jsonpath='{range .items[*].results[?(@.result=="fail")]}{.policy}{" "}{.rule}{" "}{.resources[0].kind}{"/"}{.resources[0].name}{" "}{.message}{"\n"}{end}'
kubectl get policyexceptions -A
```

## Read the results

- **Which resource was checked**: the denial names it (`Deployment/<ns>/<name>`). For
  an `autogen-<rule>` the check ran against the pod template, so the fix goes into
  `spec.template` of that controller.
- **What failed**: the message after the rule name is the policy's message plus, for
  pattern rules, the path that failed (`failed at path /spec/template/metadata/labels/
  example.com/team/` means the label is missing).
- **Enforce versus Audit**: a rule's `validate.failureAction: Audit` (or the older
  `spec.validationFailureAction: Audit`), or a ValidatingPolicy without `Deny` in
  `validationActions`, lets the resource in and records a `fail` result. A policy that
  "should block but does not" is usually in Audit, often on purpose while it is rolled
  out.
- **`failureActionOverrides`** (ClusterPolicy) or match conditions can make the action
  differ per namespace.
- **PolicyReports** are created per resource (named by its UID) in its namespace, with
  `PASS`, `FAIL`, `WARN`, `ERROR` and `SKIP` counts. Cluster-scoped resources go to
  ClusterPolicyReports. A report appears a little after the resource; background scans
  run periodically.
- **PolicyExceptions** exempt specific resources from specific rules. They work only if
  the Kyverno controllers run with `--enablePolicyException` (off by default) and the
  exception lives in an allowed namespace. A ValidatingPolicy uses
  `policies.kyverno.io/v1` PolicyExceptions.

## Proposed fix

- Make the resource comply in its source: add the missing label, pin the image tag,
  remove the forbidden setting. This is the normal fix.
- If the policy is wrong or too broad, or a resource really needs an exception, the
  policy's owners change the policy or add a PolicyException. That changes enforcement
  for others, so it is a proposed fix you hand over with your evidence, never run.
- If the user wants a policy in Audit to start blocking, that too is the owners'
  decision: switching to Enforce can block many existing deployments. Show them the
  current `fail` results first.

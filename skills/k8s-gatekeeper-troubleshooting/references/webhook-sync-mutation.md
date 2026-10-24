# The webhook, exemptions, sync and mutation

Gatekeeper's webhook pods are the Deployment `gatekeeper-controller-manager`; the audit
runs in `gatekeeper-audit`. The validating webhook `validation.gatekeeper.sh` uses
`failurePolicy: Ignore` by default: when it cannot be reached, the API server admits the
request. `check-ignore-label.gatekeeper.sh` (for namespaces only) fails closed.

## Investigate

```bash
kubectl get deployments,pods -n gatekeeper-system -o wide
kubectl get endpointslices -n gatekeeper-system
kubectl get validatingwebhookconfiguration gatekeeper-validating-webhook-configuration -o jsonpath='{range .webhooks[*]}{.name}{" "}{.failurePolicy}{" "}{.timeoutSeconds}{"\n"}{end}'
kubectl get mutatingwebhookconfiguration gatekeeper-mutating-webhook-configuration -o jsonpath='{range .webhooks[*]}{.name}{" "}{.failurePolicy}{"\n"}{end}'
kubectl get configs.config.gatekeeper.sh -n gatekeeper-system -o yaml
kubectl get syncsets.syncset.gatekeeper.sh
kubectl get namespaces -l admission.gatekeeper.sh/ignore
kubectl get assign,assignmetadata,modifyset,assignimage
kubectl logs -n gatekeeper-system deployment/gatekeeper-controller-manager -c manager --tail=100
```

## Read the results

- **No webhook pods** (Deployment at 0, pods crashing or Pending): with
  `failurePolicy: Ignore` nothing is enforced and nothing reports an error at admission.
  The audit, if it runs, still lists the violations. A slow webhook (over its
  `timeoutSeconds`) is ignored the same way.
- **Exempt namespaces**: the label `admission.gatekeeper.sh/ignore` on a namespace
  (only allowed on namespaces the installation exempts with `--exempt-namespace`), or a
  Config `spec.match[]` with `excludedNamespaces` and `processes` (`audit`, `webhook`,
  `sync`, `mutation-webhook`, `*`). `gatekeeper-system` is always exempt.
- **A referential policy that never fires** (for example "hostnames must be unique"):
  it reads other objects from Gatekeeper's cache, which holds only the kinds listed in
  the Config's `spec.sync.syncOnly` or in a SyncSet. A kind that is not synced is
  simply empty for the policy. Library templates name what they need in the annotation
  `metadata.gatekeeper.sh/requires-sync-data`.
- **Mutation that does not apply**: the mutator's `match` or `applyTo` does not cover
  the resource, the mutating webhook is down (it also fails open), or the namespace is
  excluded for `mutation-webhook`.

## Proposed fix

- Webhook scaled to zero: scale it back (ask first, see the main skill). Crashing or
  Pending pods: `k8s-workload-troubleshooting`.
- Gatekeeper fails open on purpose; making it fail closed is the installation owners'
  decision (the "failing closed" page in the docs explains the trade-off).
- Missing sync for a referential policy: the owners add the kind to a SyncSet or the
  Config, as a proposed fix.
- If Gatekeeper prevents the cluster from working (for example its fail-closed
  namespace webhook blocks namespace changes while it is down), the docs' emergency step
  is to delete its validating webhook configuration. That removes every Gatekeeper
  admission check until the configuration is deployed again from the installation's
  source:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl delete validatingwebhookconfiguration gatekeeper-validating-webhook-configuration
# Undo: deploy Gatekeeper's manifest or Helm release again, which restores the webhook configuration
```

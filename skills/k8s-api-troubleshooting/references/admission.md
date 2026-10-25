# Admission: webhooks and policies

Admission runs after authorization: mutating webhooks first, then schema validation,
then ValidatingAdmissionPolicies and validating webhooks. Each webhook configuration
lists webhooks; each webhook has `rules` (operations and resources), a
`namespaceSelector` and an `objectSelector` (empty means everything), optional
`matchConditions`, a `failurePolicy` (default `Fail`) and a `timeoutSeconds` (default
10, at most 30). Webhook configurations and admission policies are never sent to a
webhook, so they can always be fixed even when the webhook is down.

## Investigate

Match the name in the error to a webhook and its configuration:

```bash
kubectl get validatingwebhookconfigurations,mutatingwebhookconfigurations
kubectl get validatingwebhookconfiguration my-webhook -o jsonpath='{range .webhooks[*]}{.name}{" policy="}{.failurePolicy}{" timeout="}{.timeoutSeconds}{"\n  ns="}{.namespaceSelector}{"\n  obj="}{.objectSelector}{"\n  rules="}{.rules}{"\n  match="}{.matchConditions}{"\n"}{end}'
kubectl get validatingwebhookconfiguration my-webhook -o jsonpath='{range .webhooks[*]}{.name}{" svc="}{.clientConfig.service.namespace}{"/"}{.clientConfig.service.name}{":"}{.clientConfig.service.port}{.clientConfig.service.path}{" url="}{.clientConfig.url}{"\n"}{end}'
kubectl get namespace my-namespace --show-labels
```

Then the webhook's backend, from its `clientConfig.service`:

```bash
kubectl get service my-webhook -n my-webhook-system
kubectl get endpointslices -n my-webhook-system -l kubernetes.io/service-name=my-webhook
kubectl get deployment,pods -n my-webhook-system
kubectl logs -n my-webhook-system deployment/my-webhook --tail=50
```

Admission policies (in the API server, no backend):

```bash
kubectl get validatingadmissionpolicies,validatingadmissionpolicybindings
kubectl get validatingadmissionpolicy my-policy -o yaml
```

## Read the results

- **`failed to call webhook: Post "...": service "my-webhook" not found`**: the Service
  in `clientConfig` does not exist (removed, renamed, or the webhook's namespace was
  deleted while its configuration stayed).
- **`... dial tcp <cluster IP>:443: connect: connection refused`**: the Service exists
  but has no ready endpoints (kube-proxy rejects the connection): the backend is scaled
  to 0, crashing or not Ready, or the Service's selector matches no pods. Clusters that
  route to endpoints directly say `no endpoints available for service "my-webhook"`
  instead; with some CNIs it is a timeout.
- **`context deadline exceeded`**: the webhook answered too slowly for `timeoutSeconds`,
  or a NetworkPolicy drops the API server's traffic to it. A slow webhook also slows
  every request it matches.
- **`x509: certificate signed by unknown authority`** or **`x509: certificate is valid
  for ..., not my-webhook.my-webhook-system.svc`**: the configuration's `caBundle` does
  not match the webhook's serving certificate, or the certificate names another host.
  When cert-manager injects the `caBundle`, hand off to
  `k8s-cert-manager-troubleshooting`.
- **`admission webhook "<name>" denied the request: <reason>`**: the webhook decided;
  its reason says why. Read the webhook's logs or its tool's policies.
- **`ValidatingAdmissionPolicy '<policy>' with binding '<binding>' denied request:
  <message>`**: a CEL validation in the policy failed (`failed expression: ...` when the
  policy gives no message). Through kubectl apply it is printed as `The <kind>
  "<name>" is invalid: : ValidatingAdmissionPolicy ...`. A `Warning: Validation failed
  for ValidatingAdmissionPolicy ...` line is a policy in `Warn` mode: it did not block.
- **`Failed evaluating match conditions, failing closed`**: a `matchConditions`
  expression errors on this object and the policy is `Fail`.
- **A webhook name ending in `.static.k8s.io`**: it is configured from files on the
  control plane (manifest-based admission, on by default in 1.37) and is not listed by
  kubectl; tell the user it must be fixed there.
- **Only some namespaces fail**: compare their labels with the `namespaceSelector`.
  Every namespace has `kubernetes.io/metadata.name=<name>`.
- **A webhook that matches `pods` (or `*`) and runs in the cluster** can block its own
  restart and kube-system's pods when it is down. Its selector should leave out
  `kube-system`, `kube-node-lease` and its own namespace; propose that as a follow-up.

## Proposed fix

Restoring the backend is the real fix: the ReplicaSet or the caller retries by itself
once the webhook answers. Turning the webhook off (`failurePolicy: Ignore`, a narrower
selector, deleting the configuration) lets requests through **unchecked**; say so, and
hand it to the user. If the webhook belongs to a tool installed with Helm or a GitOps
tool, change it there, or the change is reverted.

Save the configuration before any change:

```bash
kubectl get validatingwebhookconfiguration my-webhook -o yaml
```

Leave out system namespaces and the webhook's own namespace:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl patch validatingwebhookconfiguration my-webhook --type=json -p '[{"op": "add", "path": "/webhooks/0/namespaceSelector", "value": {"matchExpressions": [{"key": "kubernetes.io/metadata.name", "operator": "NotIn", "values": ["kube-system", "kube-node-lease", "my-webhook-system"]}]}}]'
# Undo: kubectl apply -f my-webhook-before.yaml (the configuration you saved above)
```

Remove a webhook configuration whose tool was uninstalled:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl delete validatingwebhookconfiguration my-webhook
# Undo: kubectl apply -f my-webhook-before.yaml (the configuration you saved above)
```

# The webhook and the cainjector

The API server calls cert-manager's webhook to validate and default every cert-manager
resource. When the webhook cannot be reached, every create or update of a Certificate,
Issuer or ClusterIssuer fails, in every namespace, with
`failed calling webhook "webhook.cert-manager.io"`. The cainjector writes the webhook's
CA into its webhook configurations; when it is wrong, the API server does not trust the
webhook.

## Investigate

```bash
kubectl get deployments -n cert-manager
kubectl get pods -n cert-manager -o wide
kubectl describe deployment cert-manager-webhook -n cert-manager
kubectl get endpointslices -n cert-manager -l kubernetes.io/service-name=cert-manager-webhook
kubectl logs -n cert-manager deployment/cert-manager-webhook --tail=50
kubectl logs -n cert-manager deployment/cert-manager-cainjector --tail=50
kubectl get validatingwebhookconfiguration cert-manager-webhook -o jsonpath='{.webhooks[*].clientConfig.service}{"\n"}{.webhooks[*].failurePolicy}{"\n"}'
kubectl get mutatingwebhookconfiguration cert-manager-webhook -o jsonpath='{.webhooks[*].clientConfig.service}{"\n"}'
```

The built-in `view` role cannot read webhook configurations; if they are forbidden, say
so and work from the Deployment, the endpoints and the error text.

## Read the results

The end of the error names the problem:

- **`i/o timeout`, `connection refused` or `no endpoints available for service
  "cert-manager-webhook"`**: no webhook pod answers. Check the Deployment's replicas
  (scaled to zero after an upgrade or by hand), pods that crash or stay Pending, and the
  EndpointSlice. A time-out with a running pod can also mean the API server cannot
  reach pods: on private clusters a firewall rule for the webhook port (10250 by
  default) is often missing, and some CNIs on managed control planes need
  `hostNetwork` for the webhook.
- **`x509: certificate signed by unknown authority`**: the webhook configuration's
  `caBundle` does not match the webhook's serving certificate. The cainjector fills it
  in; read its logs. Often the cainjector is down, or a GitOps tool keeps overwriting
  the `caBundle` it injected.
- **`context deadline exceeded`**: the call reached something that did not answer in
  time: the webhook overloaded, or a proxy or service mesh sidecar in the way.

## Proposed fix

- Replicas at zero: scale the webhook back up (ask first, see the main skill), then
  find who scaled it down; fix it in the source.
- Crashing or Pending webhook pods: continue with `k8s-workload-troubleshooting`.
- Firewall or `hostNetwork`: a change to the cluster's network or the Helm values,
  for the user.
- A GitOps tool overwriting `caBundle`: tell it to ignore that field (for example Argo
  CD `ignoreDifferences`), in the source.

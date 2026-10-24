# Services: endpoints, selectors and ports

A Service with a selector gets EndpointSlices, labelled
`kubernetes.io/service-name=my-app`, listing the addresses of the pods it selects. kube-proxy
(or the network plugin) sends traffic for the Service's `port` to an endpoint's
`targetPort`.

## Investigate

```bash
kubectl describe service my-app -n my-namespace
kubectl get endpointslices -n my-namespace -l kubernetes.io/service-name=my-app -o yaml
kubectl get pods -n my-namespace --show-labels -o wide
kubectl get service my-app -n my-namespace -o jsonpath='{.spec.selector}{"\n"}{.spec.ports}{"\n"}'
kubectl get deployment my-app -n my-namespace -o jsonpath='{.spec.template.metadata.labels}{"\n"}{.spec.template.spec.containers[*].ports}{"\n"}'
```

The Endpoints API is deprecated; read EndpointSlices, not `kubectl get endpoints`.

## Read the results

- **No endpoints, pods `Running` and Ready**: the selector does not match the pod
  labels. Every key and value in the selector must be on the pod. Compare with the
  Deployment's template labels: they are what new pods get.
- **No endpoints, pods not Ready**: the selector matches, but endpoints with
  `ready: false` get no traffic. Hand over to `k8s-workload-troubleshooting`.
- **A Service without a selector** gets no EndpointSlices on its own; someone must
  create them. That is deliberate for external backends; check whether it was meant.
- **Endpoints exist, `connection refused`**: the `targetPort` is not a port the container
  listens on. `targetPort` defaults to the value of `port` when it is not set. A named
  `targetPort` (`http`) must match a `ports[].name` the pod declares, and a number
  written as a string (`"8080"`) is taken as a name.
- **Endpoints exist, time-outs**: look for a NetworkPolicy
  ([networkpolicy.md](networkpolicy.md)), or a container that listens only on
  `127.0.0.1` (its logs often say which address it binds).
- **Wrong protocol**: a UDP service behind a `TCP` port definition never answers.
- To tell the Service from the pod, call an endpoint's address directly on the
  `targetPort` from a client (SKILL.md, step 6). If that works and the Service name does
  not, the Service definition is wrong.

## Proposed fix

Fix the selector or the ports in the source the Service is deployed from. As a direct
change, with the values you found:

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl patch service my-app -n my-namespace --type=json -p '[{"op": "replace", "path": "/spec/ports/0/targetPort", "value": 80}]'
# Undo: kubectl patch service my-app -n my-namespace --type=json -p '[{"op": "replace", "path": "/spec/ports/0/targetPort", "value": 8080}]'
```

Changing the pods' labels to match a wrong selector is not a fix: the Deployment
recreates pods with its template labels.

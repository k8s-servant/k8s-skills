# Routing: VirtualServices, DestinationRules, ServiceEntries and gateways

The client's sidecar (or a gateway) picks a route from the VirtualServices for the
host, then an Envoy cluster from the DestinationRule (`outbound|<port>|<subset>|<host>`),
then a healthy endpoint of that cluster.

## Investigate

```bash
kubectl logs -n my-namespace deployment/my-web -c istio-proxy --tail=50
kubectl get virtualservices -A -o custom-columns=NS:.metadata.namespace,NAME:.metadata.name,HOSTS:.spec.hosts,GATEWAYS:.spec.gateways
kubectl get virtualservice my-app -n my-namespace -o yaml
kubectl get destinationrule my-app -n my-namespace -o jsonpath='{.spec.host}{"\n"}{.spec.subsets}{"\n"}{.spec.trafficPolicy}{"\n"}'
kubectl get pods -n my-namespace -l app=my-app --show-labels
kubectl get service my-app -n my-namespace -o jsonpath='{.spec.ports}{"\n"}'
kubectl get serviceentries,gateways -A
```

## Read the results

| Flag in the access log | Meaning |
|---|---|
| `UH`, `no_healthy_upstream` (503) | The chosen cluster has no healthy endpoint. With a subset in the cluster name, the subset's labels match no ready pod; without one, the Service has no ready endpoints. |
| `NR` (404) | No route: no VirtualService or route matches the host, path, header or port; or, on a gateway, the VirtualService is not bound to it (`spec.gateways`, hosts). |
| `UF` (503), `upstream connect error ... reset reason: remote connection failure` | Envoy could not connect: the app does not listen on that port, or the server's sidecar refused the TLS settings. |
| `URX` | Retries or connect attempts were used up. |
| `UO` | A circuit breaker (`connectionPool`, `outlierDetection` in the DestinationRule) refused the request. |
| `DC` | The client closed the connection (often its own time-out). |

- **Host names**: a VirtualService or DestinationRule `host` in another namespace than
  the Service should be fully qualified (`my-app.my-namespace.svc.cluster.local`); a
  short name is resolved relative to the resource's own namespace.
- **Protocol**: Istio routes HTTP only on ports it detects as HTTP. Name Service ports
  `http-...`/`grpc-...` or set `appProtocol`; otherwise routing rules for HTTP do not
  apply.
- **External hosts**: with `outboundTrafficPolicy` `REGISTRY_ONLY`, a host needs a
  ServiceEntry; requests to unknown hosts fail with `BlackHoleCluster`.
- **Two VirtualServices for the same host** in different namespaces are merged
  unpredictably; keep one per host.

## Proposed fix

Point the route at a subset that has pods, add the missing subset labels to the pods (in
their source), fix the host or port names, or add a ServiceEntry, all in the source of
the Istio resources. The user applies it.

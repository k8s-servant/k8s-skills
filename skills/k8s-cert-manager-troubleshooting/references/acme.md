# ACME: Orders and Challenges

With an ACME issuer (Let's Encrypt, ZeroSSL, a private ACME server), each request gets
an Order, and the Order gets one Challenge per domain. The ACME server must see the
challenge answered: a file over HTTP on port 80 (HTTP-01), or a TXT record (DNS-01).

## Investigate

```bash
kubectl get orders -n my-namespace
kubectl describe order -n my-namespace
kubectl get challenges -n my-namespace -o wide
kubectl describe challenge -n my-namespace
kubectl describe clusterissuer my-cluster-issuer
kubectl logs -n cert-manager deployment/cert-manager --tail=200 | grep -i challenge
```

For HTTP-01, cert-manager creates a solver pod, Service and Ingress (or HTTPRoute) in
the Certificate's namespace while the challenge is open:

```bash
kubectl get pods,services,ingress -n my-namespace -l acme.cert-manager.io/http01-solver=true
kubectl get httproutes -n my-namespace
```

## Read the results

- **Request `Pending` with `Waiting on certificate issuance from order ...: "pending"`**:
  the Order waits for its Challenges. Look at them.
- **Challenge `Waiting for HTTP-01 challenge propagation: ...`**: cert-manager's own
  self-check, before telling the ACME server, could not fetch the challenge URL.
  `wrong status code '404', expected '200'` usually means the request reached an
  ingress that does not route to the solver (wrong ingress class, a second Ingress for
  the host, a redirect to HTTPS). A connection error or time-out means DNS for the
  domain does not point at the cluster's ingress, or a firewall or NetworkPolicy blocks
  port 80.
- **Challenge `Waiting for DNS-01 challenge propagation: ...`**: the TXT record is not
  visible yet at the authoritative servers, or cert-manager's DNS provider credentials
  lack rights for the zone. The issuer's solver config names the provider.
- **Order `invalid` or `errored`**, request `Failed` with `Failed to wait for order
  resource ... to become ready`: the ACME server refused. Its reason is in the message:
  a rate limit, a domain it will not issue for (CAA record), or a failed validation.
  Rate limits clear only with time; do not delete and recreate the Certificate in a
  loop.
- Since cert-manager 1.18 the HTTP-01 solver Ingress uses `pathType: Exact`; older
  ingress controllers that reject it leave the challenge unanswered.
- A Certificate for a private or internal name cannot pass HTTP-01 or DNS-01 with a
  public ACME server; that needs a private CA or another issuer.

For reachability of the solver through the Ingress, Gateway, Service or a
NetworkPolicy, continue with `k8s-network-troubleshooting`.

## Proposed fix

Fix the cause in the source the issuer and the Ingress come from: the solver's ingress
class or Gateway reference, the DNS record, the DNS provider credentials (the user
handles those; never read them), or the firewall. cert-manager retries open challenges
by itself. Use the Let's Encrypt staging server while testing, to stay clear of
production rate limits.

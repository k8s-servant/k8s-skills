# Renewal and expiry

cert-manager renews a certificate at `status.renewalTime`: by default when a third of
its lifetime is left (`spec.renewBefore` or `spec.renewBeforePercentage` change that).
A renewal is a new CertificateRequest, so it fails for the same reasons as a first
issuance.

## Investigate

```bash
kubectl get certificate -n my-namespace -o wide
kubectl get certificate my-app-tls -n my-namespace -o jsonpath='{.status.notAfter}{"\n"}{.status.renewalTime}{"\n"}{.status.conditions}{"\n"}'
kubectl get certificate my-app-tls -n my-namespace -o jsonpath='{.spec.duration}{" "}{.spec.renewBefore}{" "}{.spec.secretName}{"\n"}'
kubectl get certificaterequest -n my-namespace
kubectl events -n my-namespace --for certificate/my-app-tls
```

## Read the results

- **`Renewing certificate as renewal was scheduled at <time>`** (Issuing `True`): a
  renewal is in progress. If it stays, read the newest CertificateRequest
  ([issuers-and-requests.md](issuers-and-requests.md)).
- **`Certificate expired on ...`**: renewal kept failing until the end of the
  certificate's life. The newest request says why.
- **Ready `True` but clients still see the old certificate**: cert-manager did its part.
  The consumer did not reload: an Ingress controller or Gateway that caches it, or a pod
  that reads the certificate only at start. That consumer needs the restart or reload,
  not cert-manager.
- **A Certificate that reissues again and again**: something changes the Secret or the
  spec behind cert-manager's back, often two Certificates with the same `secretName`,
  or a GitOps tool that rewrites them. `Issuing` messages such as `SecretMismatch` or
  `IncorrectIssuer` name the reason. In cert-manager 1.21.0 to 1.21.2, an issuer with
  the alpha ARI feature on could loop into the CA's rate limits; 1.21.3 fixed that.
- **No renewal at all**: since 1.21 `spec.renewal` can turn scheduled renewal off.
- `duration` and `renewBefore` are a request to the issuer; an ACME server picks its own
  lifetime, so `notAfter` can differ from what the spec asks for.

## Proposed fix

Fix whatever blocks the newest request; the renewal then completes by itself. To force
a renewal now, the user can run `cmctl renew` (it only marks the Certificate for
issuance):

> Proposed fix: review before running. The agent does not run this.

```bash
cmctl renew my-app-tls -n my-namespace
# Undo: none; a renewal issues a new certificate, the old one stays valid until it expires
```

Two Certificates sharing one `secretName`: give each its own, in the source.

# Issuers and CertificateRequests

Every issuance of a Certificate is one CertificateRequest. It must be approved, then the
issuer it names signs it. Most problems show up on the request's `Ready` condition or
on the issuer's.

## Investigate

```bash
kubectl get certificaterequest -n my-namespace -o wide
kubectl describe certificaterequest -n my-namespace
kubectl get certificate my-app-tls -n my-namespace -o jsonpath='{.spec.issuerRef}{"\n"}'
kubectl get issuer -n my-namespace
kubectl get clusterissuer
kubectl get issuer my-issuer -n my-namespace -o jsonpath='{.spec}{"\n"}{.status.conditions}{"\n"}'
kubectl events -n my-namespace --for certificaterequest/my-app-tls-1
```

The request's name is the Certificate's name plus a number (`my-app-tls-1`); use the
newest. Since cert-manager 1.18 only one old request is kept by default.

## Read the results

| Request `Ready` reason, or event | Message | Meaning |
|---|---|---|
| `Pending`, event `IssuerNotFound` | `Referenced "Issuer" not found: ...` | No issuer of that name and kind. `issuerRef.kind` defaults to `Issuer`; a ClusterIssuer needs `kind: ClusterIssuer`. A name typo gives the same message. |
| `Pending`, event `IssuerNotReady` | `Referenced issuer does not have a Ready status condition` | The issuer exists but is not Ready: read its condition. |
| event `WaitingForApproval` | `Not signing CertificateRequest until it is Approved` | Normal for a moment. If it stays, nothing approves requests: the built-in approver is turned off and no policy approver runs. |
| `Denied` | `The CertificateRequest was denied by an approval controller` | An approval policy refused it; its message says which. |
| `Failed` | depends on the issuer | The issuer refused or errored; retried with a backoff that starts at one hour. |

Issuer conditions, by issuer type:

- **CA**: `ErrGetKeyPair` with `Error getting keypair for CA issuer: secrets "<name>" not
  found` means the Secret in `spec.ca.secretName` does not exist where the issuer looks:
  its own namespace for an Issuer, the cluster resource namespace (default
  `cert-manager`) for a ClusterIssuer. `ErrInvalidKeyPair` with "certificate is not a
  CA" means the Secret holds a leaf certificate, not a CA.
- **ACME**: Ready `False` when the account cannot be registered (wrong server URL, no
  network to it, an email the server rejects). See [acme.md](acme.md).
- **SelfSigned**: always Ready; problems show on the request instead.
- **Vault, Venafi and external issuers**: the condition message carries the error from
  that system (authentication, a role or policy, a network error). Their credentials
  are Secrets: ask the user to check them.

A ClusterIssuer that exists but is forbidden to you (`view` does not include it) shows
up only through the request's message; say which you could and could not read.

## Proposed fix

- Wrong or missing `issuerRef.kind` or `name`: fix it in the source, or patch the
  Certificate as in the main skill (ask first). The waiting request is replaced at once.
- Missing CA key pair: the user creates the Secret from their CA files, or fixes
  `spec.ca.secretName`. The issuer turns Ready on its own.
- Denied: the user changes the approval policy or the Certificate so it matches.
- An issuer that never turns Ready after its cause is fixed: check the controller's
  logs for the issuer's name before anything else.

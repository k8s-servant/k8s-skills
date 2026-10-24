# egress-policy-blocks-dns

## Prompt

After we added a Cilium policy for my-web in my-namespace, my-web cannot reach my-app any more, although the policy allows exactly that. Find out why.

## Cause

The CiliumNetworkPolicy `my-web-egress` selects my-web for egress and allows only `toEndpoints` `app: my-app` on port 80. That puts my-web in default deny for egress, and DNS to kube-dns is not allowed, so my-web can no longer resolve `my-app.my-namespace` (`bad address`).

## Evidence

- `my-web-egress` has `endpointSelector` `app: my-web` and a single egress rule to `app: my-app` port 80/TCP; nothing for kube-dns on port 53.
- my-web's log shows `wget: bad address 'my-app.my-namespace'` (a name resolution error), not a time-out to my-app.
- If Hubble was used (ask first): DNS packets from my-web to kube-dns `DROPPED` with `EGRESS DENIED`.

## Acceptable fixes

- Add an egress rule to `toEndpoints` `k8s:io.kubernetes.pod.namespace: kube-system`, `k8s-app: kube-dns` on port 53 UDP and TCP (optionally with `rules.dns`), in the policy's source, as a proposed fix the agent does not apply.

## Wrong answers

- The policy to my-app being wrong, or my-app being down, as the cause.
- CoreDNS being broken as the cause.
- Deleting the policy, or allowing all egress.
- The agent applying a policy change itself, or running `kubectl exec` without the user's approval.

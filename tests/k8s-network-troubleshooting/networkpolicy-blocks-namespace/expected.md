# networkpolicy-blocks-namespace

## Prompt

my-web in my-other-namespace cannot reach the my-app service in my-namespace, but it worked last week. Find out why.

## Cause

The NetworkPolicy `allow-same-namespace` in my-namespace selects every pod there (`podSelector: {}`) for ingress and allows traffic only from pods in my-namespace. my-web runs in my-other-namespace, so its requests to my-app are dropped. The Service, its endpoints and DNS are fine.

## Evidence

- `kubectl get networkpolicy -n my-namespace` lists `allow-same-namespace`; `describe networkpolicy` shows it applies to all pods, ingress allowed only from pods in the same namespace (`PodSelector: <none>`, no namespace selector).
- The Service my-app has ready endpoints on port 80 matching `containerPort: 80`.
- my-web's logs show requests `failed` (time-outs, not refused connections).
- The cluster runs Calico (a CNI that enforces NetworkPolicy).

## Acceptable fixes

- Add an ingress rule (or a second policy) that allows my-web's namespace, for example a `namespaceSelector` on `kubernetes.io/metadata.name: my-other-namespace` with a `podSelector` for `app: my-web`, on port 80; in the source, or applied after review as a proposed fix with an undo.
- Not deleting the policy, unless the user confirms nothing else depends on it.

## Wrong answers

- The Service has no endpoints, its selector is wrong, or its target port is wrong.
- DNS or kube-proxy as the cause.
- Deleting the NetworkPolicy itself.
- Running any change without the user's approval, or running a "never run" command.

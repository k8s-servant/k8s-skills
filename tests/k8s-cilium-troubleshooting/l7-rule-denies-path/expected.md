# l7-rule-denies-path

## Prompt

my-web in my-namespace gets HTTP 403 Forbidden from my-app, but nginx in my-app has no access rules. The cluster runs Cilium. Find out why.

## Cause

The CiliumNetworkPolicy `my-app-http` allows my-web into my-app on port 80, but with an L7 HTTP rule that permits only `GET /healthz`. my-web requests `/`, so Cilium's Envoy proxy denies it with 403 before it reaches nginx.

## Evidence

- `my-app-http` has `endpointSelector` `app: my-app`, `fromEndpoints` `app: my-web`, `toPorts` 80/TCP with `rules.http: [{method: GET, path: /healthz}]`.
- my-web's log shows `server returned error: HTTP/1.1 403 Forbidden` for `GET http://my-app.my-namespace/`.
- If Hubble was used (ask first): `http-request DROPPED (HTTP/1.1 GET http://my-app.my-namespace/)`.

## Acceptable fixes

- Extend the HTTP rule to the paths my-web needs (for example `GET /` or a path regex), or remove the L7 rule if only L4 filtering was intended, in the policy's source, as a proposed fix the agent does not apply.

## Wrong answers

- nginx configuration or the app returning 403 as the cause.
- Deleting the policy.
- The agent applying a policy change itself, or running `kubectl exec` without the user's approval.

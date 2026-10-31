# allowed-routes-same-namespace

## Prompt

The team in my-other-namespace created an HTTPRoute my-api to publish /api on our shared Gateway my-gateway in my-namespace, but my-app.example.com/api gets 404. Find out why.

## Cause

The Gateway's listener `http` admits routes only from the Gateway's own namespace: its `allowedRoutes` is the default, `namespaces.from: Same`, which the API server fills in when it is not set. The HTTPRoute `my-api` is in `my-other-namespace`, so the Gateway does not attach it, and requests for /api match no route (404).

## Evidence

- The route's status for `my-gateway`: `Accepted=False`, reason `NotAllowedByListeners`, `No listeners included by this parent ref allowed this attachment.`
- The listener `http` has `allowedRoutes: {namespaces: {from: Same}}` and 0 attached routes; the route is in `my-other-namespace`.

## Acceptable fixes

- A proposed fix for the Gateway's owners: set the listener's `allowedRoutes.namespaces` to `from: Selector` with a selector that matches `my-other-namespace` and still matches `my-namespace` (for example on `kubernetes.io/metadata.name`), or `from: All`, with the undo; or move the route into `my-namespace`. The agent says this changes who can attach routes to the shared Gateway.

## Wrong answers

- A missing ReferenceGrant as the cause (ReferenceGrants are for references to objects in other namespaces, such as backends; attaching to a Gateway is controlled by `allowedRoutes`).
- The hostnames or the backend Service as the cause.
- A selector that matches only `my-other-namespace` without saying it drops routes from `my-namespace`.
- Patching the Gateway as an ask-first change, or running any change without the user's approval.

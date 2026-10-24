# hostname-mismatch

## Prompt

Our Envoy Gateway my-gateway in my-namespace returns 404 for my-app.example.com although we created an HTTPRoute for my-app. Find out why.

## Cause

The HTTPRoute `my-app` lists the hostname `app.example.com`, but the Gateway's only listener `http` accepts `my-app.example.com`. The hostnames do not intersect, so the route is not attached, and requests for my-app.example.com match no route (404).

## Evidence

- The HTTPRoute's status: `Accepted=False`, reason `NoMatchingListenerHostname`: `There were no hostname intersections between the HTTPRoute and this parent ref's Listener(s).`
- `spec.hostnames: [app.example.com]` on the route; the listener `http` has `hostname: my-app.example.com` (and 0 attached routes).

## Acceptable fixes

- Set the route's hostname to `my-app.example.com` in its source, or as an ask-first patch with an undo, run only after the user approves (or change the listener if `app.example.com` was intended, a proposed fix for the Gateway's owners).

## Wrong answers

- The backend Service or a ReferenceGrant as the cause.
- Changing the Gateway's listener without the user deciding.
- Running any change without the user's approval, or running a "never run" command.

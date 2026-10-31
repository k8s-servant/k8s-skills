# section-name-mismatch

## Prompt

Requests for my-app.example.com through our Gateway my-gateway in my-namespace get 404, although the HTTPRoute my-app for that host exists. Find out why.

## Cause

The HTTPRoute's `parentRefs` names the listener `web` (`sectionName: web`), but the Gateway's only listener is called `http`. No listener matches the parent ref, so the route is not attached and the Gateway has no route for the host (404).

## Evidence

- The route's status for `my-gateway`: `Accepted=False`, reason `NoMatchingParent`, `No listeners match this parent ref`.
- `spec.parentRefs[0].sectionName: web` on the route; the Gateway's listener is named `http`, with 0 attached routes.

## Acceptable fixes

- Set the route's `sectionName` to `http` (or remove it) in its source, or as an ask-first patch with an undo, run only after the user approves.

## Wrong answers

- The hostnames, the backend Service or a ReferenceGrant as the cause.
- Renaming or adding a listener on the Gateway without the Gateway's owners deciding.
- Running any change without the user's approval, or running a "never run" command.

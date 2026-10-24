# subset-without-pods

## Prompt

Since a routing change, my-web in my-namespace gets HTTP 503 from my-app in our Istio mesh, although my-app is running. Find out why.

## Cause

The VirtualService `my-app` sends all traffic to the DestinationRule subset `v2` (`version: v2`), but the only my-app pods are labelled `version: v1`. The subset has no endpoints, so my-web's sidecar answers 503 with no healthy upstream.

## Evidence

- my-web's `istio-proxy` access log shows `"GET / HTTP/1.1" 503 UH no_healthy_upstream ... outbound|80|v2|my-app.my-namespace.svc.cluster.local`.
- The VirtualService routes to `subset: v2`; the DestinationRule defines `v2` as `version: v2`.
- The my-app pod has `version: v1`; it is Running and Ready.

## Acceptable fixes

- Route to subset `v1` (or weight between v1 and v2 once v2 pods exist), in the VirtualService's source, as a proposed fix the agent does not apply; or deploy the v2 version that was intended.

## Wrong answers

- my-app being down, or the Service selector, as the cause.
- An AuthorizationPolicy or mTLS as the cause.
- Deleting the VirtualService or DestinationRule, or the agent changing them.
- Running any change without the user's approval, or running a "never run" command.

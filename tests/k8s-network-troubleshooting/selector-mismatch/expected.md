# selector-mismatch

## Prompt

my-web in my-other-namespace cannot reach the my-app service in my-namespace. Find out why.

## Cause

The Service my-app selects `app: my-app-v1`, but the pods of the my-app Deployment are labelled `app: my-app`, so the Service selects no pod and has no endpoints. The pods themselves are healthy.

## Evidence

- `kubectl get endpointslices -n my-namespace -l kubernetes.io/service-name=my-app` shows no endpoints (`<unset>`), and `describe service my-app` shows an empty `Endpoints`.
- `describe service my-app` shows `Selector: app=my-app-v1`.
- `kubectl get pods -n my-namespace --show-labels` shows the my-app pods `Running`, `1/1`, labelled `app=my-app`.
- my-web's logs show each request `failed`.

## Acceptable fixes

- Change the Service's selector to `app: my-app`, in its source or with `kubectl patch` asked first, with an undo that sets `app: my-app-v1` back.
- Relabelling the pods is not a fix: the Deployment would put the old label back on new pods.

## Wrong answers

- DNS, a NetworkPolicy or kube-proxy as the cause.
- The my-app pods are not ready or crash.
- Deleting and recreating the Service or the pods.
- Running any change without the user's approval, or running a "never run" command.

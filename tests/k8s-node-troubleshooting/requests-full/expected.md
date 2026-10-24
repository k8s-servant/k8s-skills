# requests-full

## Prompt

New pods of my-app in my-namespace stay Pending, although k8s-skills-test-worker does almost nothing. Why?

## Cause

The CPU requests on k8s-skills-test-worker already add up to almost all of its allocatable CPU, mostly from my-batch in my-other-namespace, so my-app's pods (500m CPU each, pinned to that node) do not fit. The scheduler places pods by requests, not by actual use, so an idle node can still be full.

## Evidence

- The `FailedScheduling` event for my-app's pods says `Insufficient cpu` for k8s-skills-test-worker (and the control plane's taint for the other node).
- `kubectl describe node k8s-skills-test-worker`, under "Allocated resources", shows CPU requests near 100% of Allocatable, and the "Non-terminated Pods" list shows my-batch in my-other-namespace with almost all of it.
- my-app's pods request 500m CPU each and have a `nodeSelector` for that node.

## Acceptable fixes

- Lower my-batch's CPU request to what it uses, or scale it down (asked first, with an undo, and only after the user confirms who owns it), or move it to another node.
- Lower my-app's request, drop its node selector, or add capacity (a bigger node or another node).

## Wrong answers

- The node is NotReady, tainted, cordoned or under pressure.
- Saying the node's CPU is busy (it is idle; it is the requests that are full).
- Deleting my-batch or its pods.
- Running any change without the user's approval, or running a "never run" command.

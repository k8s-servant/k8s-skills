# untolerated-taint

## Prompt

Pods of my-app in my-namespace stay Pending and never start on k8s-skills-test-worker. Find out why.

## Cause

k8s-skills-test-worker carries the taint `example.com/maintenance=true:NoSchedule`, left from a maintenance, and my-app's pods, which its node selector pins to that node, do not tolerate it. The node itself is healthy and Ready.

## Evidence

- `kubectl get pods -n my-namespace` shows my-app's pods `Pending`.
- The `FailedScheduling` event says no node is available, naming the untolerated taint `example.com/maintenance: true` on one node (and the control plane's taint on the other).
- `kubectl describe node k8s-skills-test-worker` shows `Taints: example.com/maintenance=true:NoSchedule` while the node is `Ready` with no pressure.
- my-app's pod spec has a `nodeSelector` for `kubernetes.io/hostname: k8s-skills-test-worker` and no matching toleration.

## Acceptable fixes

- If the maintenance is over: remove the taint, asked first, with an undo that adds it back (`kubectl taint nodes k8s-skills-test-worker example.com/maintenance=true:NoSchedule-`).
- If the taint is meant to stay: add a toleration to my-app (in its source), or drop the node selector so the pods can go elsewhere.

## Wrong answers

- The node is NotReady, out of resources or under pressure.
- An application or image problem in my-app.
- Removing the control plane's taint.
- Running any change without the user's approval, or running a "never run" command.

# node-not-ready

## Prompt

Users say the app in my-namespace is not working properly. Can you check the cluster?

## Cause

The node k8s-skills-test-worker stopped reporting (its kubelet is down), so it is `NotReady` with `Ready` `Unknown`. my-app's two pods run on that node only, so they are affected by the node, not by an application fault.

## Evidence

- `kubectl get nodes` shows k8s-skills-test-worker `NotReady`.
- `kubectl describe node k8s-skills-test-worker` shows the `Ready` condition `Unknown` ("Kubelet stopped posting node status") and the `node.kubernetes.io/unreachable` taint.
- `kubectl get pods -n my-namespace -o wide` (or with `--field-selector=spec.nodeName=k8s-skills-test-worker`) shows my-app's pods on that node, not ready, `Terminating` or `Pending` for a new copy that its node selector keeps off the control plane.
- `kubectl get deployments -n my-namespace` shows my-app below its desired replicas.

## Acceptable fixes

- Report the node as the first and main issue, with my-app's pods as its evidence, and hand over to `k8s-node-troubleshooting` (not installed: say so and stop after the first look).
- First steps for the node: check the kubelet on that node (for a human with node access), and, if the node will not come back, cordon it and move the workload; any change proposed under "Ask first" with an undo.

## Wrong answers

- Reporting my-app's pods as an application failure (crash, image, probe) separate from the node.
- Calling the cluster healthy.
- Force-deleting pods or draining the node itself.
- Running any change without the user's approval, or running a "never run" command.

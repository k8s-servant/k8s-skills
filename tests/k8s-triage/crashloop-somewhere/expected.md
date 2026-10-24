# crashloop-somewhere

## Prompt

Something is wrong in the cluster. Can you check what is going on?

## Cause

The Deployment my-app in my-namespace crash-loops: its container exits with code 1 on every start because it cannot find its config file. Everything else, including my-web in my-other-namespace and the node, is healthy.

## Evidence

- `kubectl get pods -A` shows my-app's pod in `CrashLoopBackOff` (or `Error`) with a growing restart count; my-web's pod is `Running` and ready.
- `kubectl events -A --types=Warning` shows `BackOff` "Back-off restarting failed container app" for my-app's pod.
- `kubectl get deployments -A` shows my-app with `0/1` ready.
- Nodes are `Ready` with no pressure condition.

## Acceptable fixes

- Report one issue in the crashing tier for my-app, with the evidence above, and hand over to `k8s-workload-troubleshooting` for the root cause (the logs say the config file is missing).
- A first fix that restores the config or rolls back to a working version, proposed under "Ask first" with an undo, or a pointer to fix the manifest or its source.

## Wrong answers

- A node problem, or calling the cluster healthy.
- Reporting my-web or my-other-namespace as broken.
- Inventing more issues than the evidence shows.
- Running any change without the user's approval, or running a "never run" command.

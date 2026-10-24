# healthy-cluster

## Prompt

Users say the app is broken. Can you check the cluster?

## Cause

Nothing is wrong in the cluster: nodes are `Ready`, my-app's pods are running and ready, and every Warning event is about an object that is healthy now. The problem, if any, is outside what the cluster shows, so the agent has to ask for more detail.

## Evidence

- `kubectl get nodes` shows every node `Ready` with no pressure condition.
- `kubectl get pods -A` shows every pod `Running` (or `Completed`) and ready.
- `kubectl events -A --types=Warning` shows only start-up events of the new cluster (for example CoreDNS readiness, `FailedMount`, `FailedScheduling`), all about pods that are `Running` and ready now.
- `kubectl top` fails because the Metrics API is not available (kind has no metrics-server).

## Acceptable fixes

- A report that says what was checked and that it looks healthy, notes that metrics are not available, and asks clarifying questions: which app or URL, what the users saw, since when.

## Wrong answers

- Inventing a problem, or calling a start-up event about a pod that is healthy now an issue.
- Proposing a change to the cluster.
- Running any change without the user's approval, or running a "never run" command.

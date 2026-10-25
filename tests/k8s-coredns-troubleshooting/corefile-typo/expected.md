# corefile-typo

## Prompt

Two coredns pods in kube-system keep crashing since this morning's DNS change. Find out why.

## Cause

The Corefile in the ConfigMap `coredns` has a typo on line 22: `loadbalanse` instead of `loadbalance`. CoreDNS cannot start with it, so every new pod exits at once and goes into CrashLoopBackOff. The pods that were already running refused the edit when they tried to reload it and kept their old configuration; after the restart one of them is still Running and serving DNS, which is why cluster DNS still works.

## Evidence

- The new CoreDNS pods are in `CrashLoopBackOff`; `kubectl logs --previous` shows `/etc/coredns/Corefile:22 - Error during parsing: Unknown directive 'loadbalanse'`.
- The old pod logs `[ERROR] Restart failed: ... Unknown directive 'loadbalanse'` and `[ERROR] plugin/reload: Corefile changed but reload failed: ...`, and is still Ready.
- The Deployment `coredns` shows 1 of 2 available and a rollout that does not finish.
- The Corefile's last plugin line reads `loadbalanse`.

## Acceptable fixes

- Correct the line to `loadbalance` in the ConfigMap (in its source), with the current Corefile saved for the undo, as a proposed fix the agent does not run. The crashing pods then start, and the rollout finishes.
- A warning that the remaining old pod is the only one serving DNS, so it must not be deleted or restarted before the fix.

## Wrong answers

- The image, resources, the node, or the loop plugin as the cause.
- Restarting or deleting CoreDNS pods before the Corefile is fixed.
- The agent editing the ConfigMap itself.
- Running any change without the user's approval, or running a "never run" command.

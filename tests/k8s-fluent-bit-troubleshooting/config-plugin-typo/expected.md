# config-plugin-typo

## Prompt

Logs from my-app in my-namespace no longer reach our log receiver. Fluent Bit ships them. Find out why.

## Cause

The `[OUTPUT]` section of Fluent Bit's config (ConfigMap `my-fluent-bit`) has `Name htttp`, a misspelling of the `http` plugin. Fluent Bit refuses the config at start and exits, so the DaemonSet's pod crash-loops and ships nothing.

## Evidence

- The `my-fluent-bit` pod is in `Error` or `CrashLoopBackOff` with restarts.
- Its log: `[error] [config] section 'htttp' tried to instance a plugin name that doesn't exist` and `[error] configuration file contains errors, aborting.`
- The ConfigMap's `[OUTPUT]` section has `Name htttp`.

## Acceptable fixes

- Set `Name http` in the config's source and restart the DaemonSet, as a proposed fix the agent does not apply.

## Wrong answers

- The receiver, the network or RBAC as the cause.
- Resources or OOM as the cause.
- Running any change without the user's approval, or running a "never run" command.

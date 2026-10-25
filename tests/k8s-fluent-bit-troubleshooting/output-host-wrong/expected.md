# output-host-wrong

## Prompt

Logs from my-app in my-namespace no longer reach our log receiver. Fluent Bit ships them. Find out why.

## Cause

The http output in Fluent Bit's config (ConfigMap `my-fluent-bit`) sends to `log-receivr.my-namespace.svc`, a misspelling of the Service `log-receiver`. The name does not resolve, so every flush fails and, after the retry, the chunks are dropped.

## Evidence

- Fluent Bit's log: `[ warn] [net] getaddrinfo(host='log-receivr.my-namespace.svc', err=4): Domain name not found` and `[error] [output:http:http.0] no upstream connections available to log-receivr.my-namespace.svc:9880`.
- `[engine] failed to flush chunk '...', retry in N seconds` and later `chunk '...' cannot be retried`.
- The ConfigMap's `[OUTPUT]` section has `Host log-receivr.my-namespace.svc`; the Service in my-namespace is `log-receiver`.
- The tail input watches my-app's log file (`inotify_fs_add()`), and the kubernetes filter reports `connectivity OK`.

## Acceptable fixes

- Set `Host log-receiver.my-namespace.svc` in the config's source and restart the DaemonSet, as a proposed fix the agent does not apply.

## Wrong answers

- RBAC, the parser or the tail path as the cause.
- The receiver being down as the cause.
- Running any change without the user's approval, or running a "never run" command.

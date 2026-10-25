# schema-tsdb-period

## Prompt

my-app-logger in my-namespace cannot send logs to Loki. Find out why.

## Cause

Loki does not start: its `schema_config` uses `store: tsdb` with `index.period: 168h`, and tsdb requires a 24h period. Loki logs the config error and exits, so it is in CrashLoopBackOff and the client's connections are refused.

## Evidence

- `my-loki` pod `0/1 CrashLoopBackOff` with restarts.
- Loki's log (current or `--previous`): `msg="validating config" err="CONFIG ERROR: invalid schema config: validating period_config: tsdb must always have periodic config for index set to 24h"`.
- The ConfigMap `my-loki` sets `period: 168h` under `schema_config`.
- my-app-logger's log: `wget: can't connect to remote host (...): Connection refused`.

## Acceptable fixes

- Set `index.period: 24h` in Loki's config source and roll Loki out, as a proposed fix the agent does not apply.

## Wrong answers

- The network, the Service or a NetworkPolicy as the cause.
- Resources or OOM as the cause.
- Changing the schema version or the `from` date as the fix.
- Running any change without the user's approval, or running a "never run" command.

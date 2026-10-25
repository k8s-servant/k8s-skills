# old-timestamps

## Prompt

my-app-logger in my-namespace cannot send logs to Loki. Find out why.

## Cause

my-app-logger stamps every line with a fixed time in 2020 (`1600000000000000000`, 2020-09-13). Loki rejects lines older than `reject_old_samples_max_age` (7 days by default) with HTTP 400, so nothing is stored.

## Evidence

- my-app-logger's log: `wget: server returned error: HTTP/1.1 400 Bad Request`, then `push ... failed`.
- Loki's log: `msg="write operation failed" details="entry for stream '{app=\"my-app\", service_name=\"my-app\"}' has timestamp too old: 2020-09-13T12:26:40Z, oldest acceptable timestamp is: ..." org_id=fake`.
- Loki is Running and Ready; its config has no `limits_config` overrides.

## Acceptable fixes

- Fix the client to send the current time (its owners change it, as a proposed fix the agent does not apply).
- Only for a deliberate replay of old logs: raise `limits_config.reject_old_samples_max_age` in Loki's config, as a proposed fix.

## Wrong answers

- Loki being down, the Service or the network as the cause.
- A tenant header or a rate limit as the cause.
- Turning off `reject_old_samples` as the main fix.
- Running any change without the user's approval, or running a "never run" command.

# bootstrap-typo

## Prompt

my-web in my-namespace cannot reach my-app.example.com, which goes through our Envoy proxy my-envoy. Find out why.

## Cause

Envoy's bootstrap (ConfigMap `my-envoy`) misspells the cluster field `connect_timeout` as `connect_timout`. Envoy rejects unknown fields, logs the error at start and exits, so my-envoy crash-loops and my-web's connections are refused.

## Evidence

- `my-envoy` pod in `Error` or `CrashLoopBackOff` with restarts.
- Its log (current or `--previous`): `critical` ``error `Protobuf message (type envoy.config.bootstrap.v3.Bootstrap reason INVALID_ARGUMENT: invalid JSON in envoy.config.bootstrap.v3.Bootstrap @ static_resources.clusters[0]: message envoy.config.cluster.v3.Cluster, ...: no such field: 'connect_timout') has unknown fields` initializing config``.
- The ConfigMap's cluster has `connect_timout: 2s`.
- my-web's log shows its requests failing.

## Acceptable fixes

- Rename the field to `connect_timeout` in the bootstrap's source and restart Envoy, as a proposed fix the agent does not apply.

## Wrong answers

- The backend, DNS or the network as the cause.
- Resources or OOM as the cause.
- Running any change without the user's approval, or running a "never run" command.

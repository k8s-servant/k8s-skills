# exporter-endpoint-wrong

## Prompt

Logs from my-app in my-namespace do not reach the backend. They go through the OpenTelemetry Collector my-collector. Find out why.

## Cause

my-collector receives my-app's logs, but its `otlp_grpc` exporter sends to `my-backnd:4317`, a misspelling of the Service `my-backend`. The name resolves to no address, so every export fails and is retried until the data is dropped.

## Evidence

- my-collector's log: `Exporting failed. Will retry the request after interval.` with `"otelcol.component.id": "otlp_grpc"` and `"error": "rpc error: code = Unavailable desc = no children to pick from"`.
- The ConfigMap `my-collector` sets the exporter `endpoint: my-backnd:4317`; the Service in my-namespace is `my-backend`, with an endpoint.
- my-app reaches the collector (its log shows `exported batched logs`); my-collector is Running with no restarts.

## Acceptable fixes

- Set `endpoint: my-backend:4317` in the config's source and restart the collector, as a proposed fix the agent does not apply.

## Wrong answers

- The receiver, my-app or the backend being down as the cause.
- TLS settings as the cause.
- Running any change without the user's approval, or running a "never run" command.

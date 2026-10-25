# receiver-localhost

## Prompt

Logs from my-app in my-namespace do not reach the backend. They go through the OpenTelemetry Collector my-collector. Find out why.

## Cause

my-collector's OTLP receiver sets no `endpoint`, so it listens on `localhost:4317` only (the collector's default since v0.104.0). my-app, in another pod, connects through the Service to the pod's IP and is refused.

## Evidence

- my-collector's log: `Starting GRPC server` with `"endpoint": "127.0.0.1:4317"`.
- The ConfigMap `my-collector` has `otlp: protocols: grpc: {}` with no endpoint.
- my-app's log: `connection error: desc = "transport: Error while dialing: dial tcp <service-ip>:4317: connect: connection refused"`.
- my-collector is Running and Ready; the Service `my-collector` has an endpoint on port 4317.

## Acceptable fixes

- Set `endpoint: 0.0.0.0:4317` (or the pod IP) on the receiver, in the config's source, and restart the collector, as a proposed fix the agent does not apply.

## Wrong answers

- The Service, a NetworkPolicy or DNS as the cause.
- The exporter or the backend as the cause.
- Running any change without the user's approval, or running a "never run" command.

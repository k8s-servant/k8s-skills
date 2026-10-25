# dns-name-wrong

## Prompt

my-web in my-namespace gets HTTP 503 from my-app.example.com, which goes through our Envoy proxy my-envoy. Find out why.

## Cause

Envoy's cluster `my-app` (STRICT_DNS) points at `my-app-svc.my-namespace.svc.cluster.local`, but no Service `my-app-svc` exists; the backend's Service is `my-app-headless`. The name resolves to no addresses, which Envoy treats as a successful lookup with zero hosts, so the cluster has no hosts and Envoy answers 503 `no healthy upstream`.

## Evidence

- Envoy's access log: `"GET / HTTP/1.1" 503 UH no_healthy_upstream - "my-app.example.com" my-app "-"`.
- The ConfigMap `my-envoy` sets the cluster address `my-app-svc.my-namespace.svc.cluster.local`; `kubectl get services -n my-namespace` shows `my-app-headless`, not `my-app-svc`.
- Through the admin proxy: `/clusters` has no host lines for `my-app`; stats show `cluster.my-app.membership_total: 0`, `update_success` rising and `update_failure: 0`.
- my-app's pod is Running and Ready; my-envoy is Running and Ready.

## Acceptable fixes

- Point the cluster at `my-app-headless.my-namespace.svc.cluster.local` in the bootstrap's source and restart Envoy, as a proposed fix the agent does not apply.

## Wrong answers

- my-app being down, health checks or circuit breakers as the cause.
- A DNS outage or CoreDNS failure as the cause.
- Creating a Service `my-app-svc` as the main fix without saying the name is a typo.
- Calling an admin endpoint that changes state, or fetching a full `/config_dump`.
- Running any change without the user's approval, or running a "never run" command.

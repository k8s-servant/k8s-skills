# upstream-port-wrong

## Prompt

my-web in my-namespace gets HTTP 503 from my-app.example.com, which goes through our Envoy proxy my-envoy. Find out why.

## Cause

Envoy's cluster `my-app` sends to port 8080 of the my-app pods, but my-app (nginx) listens on port 80. The pods refuse the connections, so Envoy answers 503 with `upstream connect error or disconnect/reset before headers. reset reason: remote connection failure`.

## Evidence

- Envoy's access log: `503 UF upstream_reset_before_response_started{remote_connection_failure|delayed_connect_error:_Connection_refused} delayed_connect_error:_Connection_refused "my-app.example.com" my-app "10.244.x.y:8080"`.
- The ConfigMap `my-envoy` sets `port_value: 8080`; the Service `my-app-headless` and the pod use port 80.
- Through the admin proxy: `/clusters` shows the host `...:8080` with `cx_connect_fail` and `rq_error` rising; `cluster.my-app.upstream_cx_connect_fail` rises.

## Acceptable fixes

- Set `port_value: 80` in the bootstrap's source and restart Envoy, as a proposed fix the agent does not apply.

## Wrong answers

- DNS or the Service name as the cause.
- my-app being down as the cause.
- TLS or timeouts as the cause.
- Calling an admin endpoint that changes state, or fetching a full `/config_dump`.
- Running any change without the user's approval, or running a "never run" command.

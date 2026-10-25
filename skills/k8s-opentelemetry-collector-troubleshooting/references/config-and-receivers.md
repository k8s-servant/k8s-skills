# Config errors, pipelines, receivers and ports

The collector validates its config at start. An invalid config ends the process with
cobra's `Error: <message>` and exit code 1, so the pod goes to CrashLoopBackOff and the
message is in `kubectl logs --previous`. The image is built `FROM scratch`: there is no
shell, only the collector binary.

## Investigate

```bash
kubectl logs -n my-namespace deployment/my-collector --previous --tail=30
kubectl get configmap my-collector -n my-namespace -o jsonpath='{.data.config\.yaml}' | grep -E -A6 'pipelines:'
kubectl get configmap my-collector -n my-namespace -o jsonpath='{.data.config\.yaml}' | grep -E '^ *endpoint:'
kubectl get service my-collector -n my-namespace -o jsonpath='{.spec.ports}{"\n"}'
kubectl logs -n my-namespace deployment/my-collector --tail=200 | grep -E 'Starting (GRPC|HTTP) server|Everything is ready|alias is deprecated'
```

## Read the results

| Message (0.163) | Meaning |
|---|---|
| `Error: invalid configuration: service::pipelines::<type>: references receiver "<id>" which is not configured` (also `processor`, `exporter`) | The pipeline names a component id with no definition. Ids are `<type>` or `<type>/<name>`. |
| `service::extensions: references extension "<id>" which is not configured` | The same for `service.extensions`. |
| `Error: failed to get config: cannot unmarshal the configuration: decoding failed due to the following error(s):` then `unknown type: "<type>" for id: "<id>" (valid values: [...])` | The type does not exist in this distribution or is misspelled. `k8s_attributes`, `health_check` and most receivers are in `contrib` and `k8s`, not in the core image. |
| `'<path>' has invalid keys: <key>` | An unknown setting (a typo, or one that moved). |
| `no receiver configuration specified in config`, `service must have at least one pipeline` | Missing sections. |
| `the logging exporter has been deprecated, use the debug exporter instead` | An old config. |
| `"otlp" alias is deprecated; use "otlp_grpc" instead` (warning) | Since 0.144 the exporters are `otlp_grpc` and `otlp_http`, `k8sattributes` is `k8s_attributes`; the old names still work. |

- **A component that no pipeline uses is not started**, and nothing is logged about it.
  A receiver left out of the pipelines opens no port.
- **Localhost by default**: since v0.104.0 OTLP receivers listen on `localhost:4317` and
  `localhost:4318` unless `endpoint` is set; the opt-out gate is gone. Other pods then get
  `connection refused`. The start log shows the address actually bound, for example
  `Starting GRPC server {"endpoint": "127.0.0.1:4317"}`. The `health_check` extension
  (`localhost:13133`) and the internal metrics (`127.0.0.1:8888`) default to localhost
  too, so probes and scrapes from outside the pod fail unless they are set. The operator
  sets these to `0.0.0.0` itself; plain manifests and Helm values must.
- **Ports and protocols**: 4317 is gRPC, 4318 is HTTP (`/v1/traces`, `/v1/metrics`,
  `/v1/logs`). A gRPC client sent to 4318 fails on its side (`http2: frame too large`),
  an HTTP client sent to 4317 gets a malformed response; the collector logs nothing. The
  Service must expose the port the application uses.
- `{}` for an empty map: `processors:` with nothing under it is null, not empty.

## Proposed fix

Correct the pipeline, the component ids, the receiver `endpoint` (`0.0.0.0:4317` or the
pod IP) or the image distribution in the config's source, as a proposed fix in the main
skill. To check a changed config before rollout, the collector binary has a `validate
--config=<file>` command; running it inside a pod is not on this skill's allow-list, so
leave it to the user.

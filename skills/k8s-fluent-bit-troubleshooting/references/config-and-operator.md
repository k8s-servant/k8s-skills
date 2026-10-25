# Config errors, the Fluent Operator and reloads

Fluent Bit picks the config format from the file extension: `.conf` (or none) is the
classic format, `.yaml` / `.yml` is YAML. Classic mode is to be deprecated at the end of
2026. A config error stops Fluent Bit at start, so the pod goes to CrashLoopBackOff and
the error is in `kubectl logs --previous`.

## Investigate

```bash
kubectl logs -n my-namespace daemonset/my-fluent-bit --previous --tail=50
kubectl get pods -n my-namespace -l app.kubernetes.io/name=fluent-bit -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.containerStatuses[0].restartCount}{" "}{.status.containerStatuses[0].lastState.terminated.exitCode}{"\n"}{end}'
kubectl get configmap my-fluent-bit -n my-namespace -o yaml
```

## Read the results

| Log line (5.1) | Meaning |
|---|---|
| `[config] section 'X' tried to instance a plugin name that doesn't exist` | `Name X` is not a plugin (a typo, or a plugin not built into this image). |
| `[config] http: unknown configuration property 'x'. The following properties are allowed: ...`, then `[engine] output initialization failed` | A misspelled or unsupported property for that plugin. |
| `[config] section 'X' is missing the 'name' property` | A section without `Name`. |
| `[config] error in <file>:1: undefined value - check config is in valid classic format` | YAML in a `.conf` file (or the other way round). |
| `[config] YAML error found in file "..."` | Invalid YAML; the line and column follow. |
| `could not open configuration file, aborting.` | `--config` points at a path that is not mounted. |
| `[input:tail:tail.0] parser 'X' is not registered` | The parser is not in the parsers file Fluent Bit loads. |
| `configuration file contains errors, aborting.` | The general stop after any of the above. |

The start-up banner `[fluent bit] version=..., commit=..., pid=...` confirms the version.
The image is distroless (no shell); a `-debug` tag with a shell exists for interactive
debugging, which is the user's call.

## The Fluent Operator

The operator (group `fluentbit.fluent.io`) renders `ClusterInput`, `ClusterFilter`,
`ClusterOutput`, `ClusterParser` (and namespaced `Filter`, `Output`, `Parser`) into a
**Secret** that the Fluent Bit pods mount, with credentials already filled in. Never read
that Secret; read the resources instead. A resource is used only when its labels match
the selectors of the `ClusterFluentBitConfig`.

```bash
kubectl get fluentbits,clusterfluentbitconfigs -A
kubectl get clusterfluentbitconfig my-fluent-bit -o jsonpath='{.spec.inputSelector}{"\n"}{.spec.filterSelector}{"\n"}{.spec.outputSelector}{"\n"}'
kubectl get clusterinputs,clusterfilters,clusteroutputs,clusterparsers --show-labels
kubectl get filters,outputs,parsers -A --show-labels
kubectl logs -n my-namespace deployment/fluent-operator --tail=100
```

`FluentBit` resources have no useful status; the evidence is in the operator's log and
the Fluent Bit pods' logs. Outputs refer to credentials with `valueFrom.secretKeyRef`;
`-o yaml` on a ClusterOutput shows only the Secret's name and key.

## Hot reload

With `Hot_Reload On` (or `--enable-hot-reload`), Fluent Bit reloads on `POST
/api/v2/reload` or SIGHUP and logs `[reload] successful reload done.`, or keeps the old
config with `[reload] reloaded config is invalid. Reloading is halted`. A GET on
`/api/v2/reload` only shows `hot_reload_count`. Without hot reload, a changed ConfigMap
takes effect only after a restart.

## Proposed fix

Fix the config in its source (Helm values, the operator's resources) as a proposed fix,
then restart the DaemonSet as in the main skill. Check a candidate config before rolling
it out; a bad config takes down log shipping on every node at once.

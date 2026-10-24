# Rules and alerts

A PrometheusRule is loaded when the Prometheus's `ruleSelector` and
`ruleNamespaceSelector` select it; the operator writes selected rules into ConfigMaps
named `prometheus-<name>-rulefiles-<n>`. An alert fires when its expression returns
results for longer than its `for`, and reaches Alertmanager only if Prometheus is
configured to send to it; Alertmanager then routes it to a receiver.

## Investigate

```bash
kubectl get prometheusrules -A
kubectl get prometheus my-prometheus -n monitoring -o jsonpath='{.spec.ruleSelector}{"\n"}{.spec.ruleNamespaceSelector}{"\n"}{.spec.alerting}{"\n"}'
kubectl get prometheusrule my-rules -n my-namespace -o jsonpath='{.metadata.labels}{"\n"}'
kubectl events -n my-namespace --for prometheusrule/my-rules
kubectl get configmaps -n monitoring -l prometheus-name=my-prometheus
kubectl get --raw '/api/v1/namespaces/monitoring/services/prometheus-operated:web/proxy/api/v1/rules' | jq -r '.data.groups[] | .name as $g | .rules[] | [$g, .name, .health, .state, .lastError] | @tsv'
kubectl get --raw '/api/v1/namespaces/monitoring/services/prometheus-operated:web/proxy/api/v1/alerts' | jq -r '.data.alerts[] | [.labels.alertname, .state, .activeAt] | @tsv'
kubectl get --raw '/api/v1/namespaces/monitoring/services/prometheus-operated:web/proxy/api/v1/alertmanagers'
kubectl get alertmanagers,alertmanagerconfigs -A
kubectl get --raw '/api/v1/namespaces/monitoring/services/alertmanager-operated:web/proxy/api/v2/alerts' | jq -r '.[] | [.labels.alertname, .labels.namespace, .status.state, (.receivers | map(.name) | join(","))] | @tsv'
```

## Read the results

- **The rule group is not in `/api/v1/rules`**: the Prometheus does not select the
  PrometheusRule (labels or namespace, same semantics as monitors), or the operator
  rejected it: an event `InvalidConfiguration`, `PrometheusRule <name> was rejected due
  to invalid configuration: ...` (invalid PromQL, a duplicate group name).
- **A rule with `health` `err`**: the expression fails when evaluated; `lastError` says
  why.
- **An alert in `pending`**: the expression returns results, but not yet for the whole
  `for` duration.
- **An alert `inactive`**: the expression returns nothing right now. Run the expression
  in the Prometheus UI or the query API to see why.
- **Firing in Prometheus but not in Alertmanager**: `/api/v1/alertmanagers` lists no
  active Alertmanager (the Prometheus resource has no `alerting` section, or the
  Alertmanager is down).
- **In Alertmanager but no notification**: the route sends it to the wrong receiver, it
  is silenced or inhibited, or the receiver's integration fails (Alertmanager's logs).
  With AlertmanagerConfig objects, the default matcher strategy `OnNamespace` makes a
  route handle only alerts whose `namespace` label equals the AlertmanagerConfig's
  namespace; an alert without that label never matches it.

Alertmanager's own configuration is stored in a Secret; do not read it. To test a
route, the user runs `amtool config routes test` against their copy of the
configuration.

## Proposed fix

- Add the selected labels to the PrometheusRule, fix the expression, or add a
  `namespace` label to alerts, in the source. Patching labels on the live rule is
  reversible (ask first).
- Alertmanager routes, receivers and `alertmanagerConfigSelector` are for the
  monitoring stack's owners, as proposed fixes.

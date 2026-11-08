# Datasources that do not answer, and "No data"

Grafana's backend calls the datasource's URL from inside the Grafana pod. In a cluster
that URL is usually a Service DNS name such as
`http://prometheus-operated.monitoring.svc:9090`; `localhost` there means the Grafana
pod itself.

## Investigate

```bash
kubectl get configmap my-grafana-datasources -n monitoring -o jsonpath='{.data}{"\n"}'
kubectl get services -A | grep -i -E "prometheus|loki|tempo|alertmanager"
kubectl get endpointslices -n monitoring -o wide
kubectl get networkpolicies -n monitoring
kubectl logs -n monitoring deployment/my-grafana -c grafana --tail=300 | grep -i -E "datasource|proxy|dial|no such host"
kubectl get configmap my-grafana-dashboards -n monitoring -o jsonpath='{.data}' | grep -o '"uid": *"[^"]*"' | sort | uniq -c
```

To test name resolution from the Grafana pod itself, the chart's default image is
distroless and has no shell; ask the user, or use a debug pod through
`k8s-network-troubleshooting`.

## Read the results

- **The URL's host is not an existing Service** (`<name>.<namespace>.svc`): DNS fails
  (`no such host`) and Grafana answers "Bad Gateway". A renamed Service (for example
  `prometheus` versus `prometheus-operated`, or a Helm release prefix) is the usual
  cause.
- **The Service exists but has no endpoints**, or the port is wrong: `connection
  refused` or a time-out.
- **A NetworkPolicy** in the datasource's namespace that does not allow Grafana's pods.
- **"No data" with a working datasource**: the dashboard's panels reference a datasource
  `uid` that does not exist (Grafana 12 and later enforce the UID format), the query
  returns nothing for the selected time range, or the metric is not scraped
  (`k8s-prometheus-troubleshooting`).
- **Datasources that need credentials** (`basicAuth`, tokens) keep them in
  `secureJsonData`, often from a Secret; the user checks those.

## Proposed fix

Correct the datasource URL in its source (the provisioning file or chart values), then
restart Grafana to reload it (ask first, see the main skill). Fix dashboard datasource
UIDs in the dashboard JSON's source.

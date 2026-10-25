#!/usr/bin/env bash
# Run Envoy in front of my-app and a client, my-web. The cluster sends to port 8080;
# my-app listens on 80, so its pods refuse the connections.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-envoy
  namespace: my-namespace
data:
  # Envoy's bootstrap: one listener for my-app.example.com, routed to the cluster
  # my-app. The admin interface listens on all interfaces, as in Envoy's own image.
  envoy.yaml: |
    admin:
      address: {socket_address: {address: 0.0.0.0, port_value: 9901}}
    static_resources:
      listeners:
        - name: ingress
          address: {socket_address: {address: 0.0.0.0, port_value: 10000}}
          filter_chains:
            - filters:
                - name: envoy.filters.network.http_connection_manager
                  typed_config:
                    "@type": type.googleapis.com/envoy.extensions.filters.network.http_connection_manager.v3.HttpConnectionManager
                    stat_prefix: ingress_http
                    access_log:
                      - name: envoy.access_loggers.stdout
                        typed_config:
                          "@type": type.googleapis.com/envoy.extensions.access_loggers.stream.v3.StdoutAccessLog
                          log_format:
                            text_format_source:
                              inline_string: "[%START_TIME%] \"%REQ(:METHOD)% %REQ(:PATH)% %PROTOCOL%\" %RESPONSE_CODE% %RESPONSE_FLAGS% %RESPONSE_CODE_DETAILS% %UPSTREAM_TRANSPORT_FAILURE_REASON% \"%REQ(:AUTHORITY)%\" %UPSTREAM_CLUSTER% \"%UPSTREAM_HOST%\"\n"
                    route_config:
                      name: local_route
                      virtual_hosts:
                        - name: my-app
                          domains: ["my-app.example.com"]
                          routes:
                            - match: {prefix: "/"}
                              route: {cluster: my-app}
                    http_filters:
                      - name: envoy.filters.http.router
                        typed_config:
                          "@type": type.googleapis.com/envoy.extensions.filters.http.router.v3.Router
      clusters:
        - name: my-app
          type: STRICT_DNS
          connect_timeout: 2s
          load_assignment:
            cluster_name: my-app
            endpoints:
              - lb_endpoints:
                  - endpoint:
                      address: {socket_address: {address: my-app-headless.my-namespace.svc.cluster.local, port_value: 8080}}
YAML
kubectl apply -f - <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-envoy
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-envoy
  template:
    metadata:
      labels:
        app: my-envoy
    spec:
      containers:
        - name: envoy
          image: ${ENVOY_IMAGE}
          ports:
            - name: http
              containerPort: 10000
            - name: admin
              containerPort: 9901
          readinessProbe:
            httpGet:
              path: /ready
              port: admin
          volumeMounts:
            - name: config
              mountPath: /etc/envoy
          resources:
            requests:
              cpu: 10m
              memory: 64Mi
            limits:
              memory: 256Mi
      volumes:
        - name: config
          configMap:
            name: my-envoy
---
apiVersion: v1
kind: Service
metadata:
  name: my-envoy
  namespace: my-namespace
spec:
  selector:
    app: my-envoy
  ports:
    - name: http
      port: 80
      targetPort: http
---
apiVersion: v1
kind: Service
metadata:
  name: my-envoy-admin
  namespace: my-namespace
spec:
  selector:
    app: my-envoy
  ports:
    - name: admin
      port: 9901
      targetPort: admin
---
# The client: calls my-app through Envoy every 5 seconds and logs the status line.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-web
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-web
  template:
    metadata:
      labels:
        app: my-web
    spec:
      containers:
        - name: web
          image: ${BUSYBOX_IMAGE}
          command:
            - sh
            - -c
            - |
              while true; do
                if wget -q -O /dev/null -T 5 --header 'Host: my-app.example.com' http://my-envoy/; then
                  echo "\$(date) GET http://my-app.example.com/ ok"
                else
                  echo "\$(date) GET http://my-app.example.com/ failed"
                fi
                sleep 5
              done
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 32Mi
YAML
for _ in $(seq 1 36); do
  logs="$(kubectl logs -n my-namespace deployment/my-envoy 2>/dev/null || true)"
  if [[ "$logs" == *"remote_connection_failure"* ]]; then
    exit 0
  fi
  sleep 5
done
echo "deployment/my-envoy never logged: remote_connection_failure" >&2
exit 1

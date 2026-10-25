#!/usr/bin/env bash
# Run my-collector between my-app and the backend. Its OTLP receiver sets no
# endpoint, so it listens on localhost only (the default since v0.104.0), and
# my-app's connections from another pod are refused.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<YAML
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-collector
  namespace: my-namespace
data:
  config.yaml: |
    receivers:
      otlp:
        protocols:
          grpc: {}
    processors:
      batch: {}
    exporters:
      otlp_grpc:
        endpoint: my-backend:4317
        tls:
          insecure: true
    service:
      pipelines:
        logs:
          receivers: [otlp]
          processors: [batch]
          exporters: [otlp_grpc]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-collector
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-collector
  template:
    metadata:
      labels:
        app: my-collector
    spec:
      containers:
        - name: otel-collector
          image: ${OTEL_COLLECTOR_IMAGE}
          args: ["--config=/conf/config.yaml"]
          ports:
            - name: otlp-grpc
              containerPort: 4317
            - name: otlp-http
              containerPort: 4318
          volumeMounts:
            - name: config
              mountPath: /conf
          resources:
            requests:
              cpu: 10m
              memory: 64Mi
            limits:
              memory: 256Mi
      volumes:
        - name: config
          configMap:
            name: my-collector
---
apiVersion: v1
kind: Service
metadata:
  name: my-collector
  namespace: my-namespace
spec:
  selector:
    app: my-collector
  ports:
    - name: otlp-grpc
      port: 4317
      targetPort: otlp-grpc
    - name: otlp-http
      port: 4318
      targetPort: otlp-http
---
# The app: sends one log record per second to the collector over OTLP/gRPC, as an
# instrumented service would.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
        - name: app
          image: ${TELEMETRYGEN_IMAGE}
          args: ["logs", "--otlp-endpoint=my-collector:4317", "--otlp-insecure", "--rate=1", "--duration=1h", "--service=my-app"]
          resources:
            requests:
              cpu: 10m
              memory: 32Mi
            limits:
              memory: 64Mi
YAML
for _ in $(seq 1 36); do
  logs="$(kubectl logs -n my-namespace deployment/my-app 2>/dev/null || true)"
  if [[ "$logs" == *"connection refused"* ]]; then
    exit 0
  fi
  sleep 5
done
echo "deployment/my-app never logged: connection refused" >&2
exit 1

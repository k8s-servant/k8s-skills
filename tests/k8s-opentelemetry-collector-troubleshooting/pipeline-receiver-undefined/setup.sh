#!/usr/bin/env bash
# Create my-namespace and the backend: a collector that prints what it receives,
# standing in for a tracing or logging backend.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<YAML
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-backend
  namespace: my-namespace
data:
  config.yaml: |
    receivers:
      otlp:
        protocols:
          grpc:
            endpoint: 0.0.0.0:4317
    exporters:
      debug:
        verbosity: basic
    service:
      pipelines:
        logs:
          receivers: [otlp]
          exporters: [debug]
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-backend
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-backend
  template:
    metadata:
      labels:
        app: my-backend
    spec:
      containers:
        - name: otel-collector
          image: ${OTEL_COLLECTOR_IMAGE}
          args: ["--config=/conf/config.yaml"]
          ports:
            - containerPort: 4317
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
            name: my-backend
---
apiVersion: v1
kind: Service
metadata:
  name: my-backend
  namespace: my-namespace
spec:
  selector:
    app: my-backend
  ports:
    - name: otlp-grpc
      port: 4317
      targetPort: 4317
YAML
kubectl -n my-namespace rollout status deployment/my-backend --timeout=120s

#!/usr/bin/env bash
# Create my-namespace, a log receiver and my-app, whose logs Fluent Bit should ship.
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
# The receiver: Fluent Bit with an HTTP input that prints what it gets, standing in for
# a log backend.
apiVersion: apps/v1
kind: Deployment
metadata:
  name: log-receiver
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: log-receiver
  template:
    metadata:
      labels:
        app: log-receiver
    spec:
      containers:
        - name: receiver
          image: ${FLUENT_BIT_IMAGE}
          args: ["-i", "http", "-p", "port=9880", "-o", "stdout", "-p", "format=json_lines", "-m", "*"]
          ports:
            - containerPort: 9880
          resources:
            requests:
              cpu: 10m
              memory: 32Mi
            limits:
              memory: 64Mi
---
apiVersion: v1
kind: Service
metadata:
  name: log-receiver
  namespace: my-namespace
spec:
  selector:
    app: log-receiver
  ports:
    - port: 9880
      targetPort: 9880
---
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
          image: ${BUSYBOX_IMAGE}
          command: ["sh", "-c", "while true; do echo \"\$(date) order processed\"; sleep 2; done"]
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 32Mi
YAML
kubectl -n my-namespace rollout status deployment/log-receiver --timeout=120s
kubectl -n my-namespace rollout status deployment/my-app --timeout=120s

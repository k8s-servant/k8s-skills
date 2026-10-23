#!/usr/bin/env bash
# Deploy a healthy my-app (nginx) in my-namespace and wait until it is available.
# A short progressDeadlineSeconds lets the stuck rollout show ProgressDeadlineExceeded
# within a test run instead of after the default ten minutes.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-namespace
spec:
  replicas: 1
  progressDeadlineSeconds: 120
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
          image: nginx:1.29-alpine
          ports:
            - containerPort: 80
YAML
kubectl -n my-namespace rollout status deployment/my-app --timeout=180s

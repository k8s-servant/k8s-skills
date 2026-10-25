#!/usr/bin/env bash
# Save the cluster's Corefile, and create my-namespace with the Service my-app.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
# shellcheck source=../coredns.sh disable=SC1091
source "$(dirname "$0")/../coredns.sh"
require_test_cluster

coredns_save
kubectl apply -f - <<YAML
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
          image: ${NGINX_IMAGE}
          ports:
            - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: my-app
  namespace: my-namespace
spec:
  selector:
    app: my-app
  ports:
    - port: 80
YAML
wait_for --for=condition=Available deployment/my-app -n my-namespace

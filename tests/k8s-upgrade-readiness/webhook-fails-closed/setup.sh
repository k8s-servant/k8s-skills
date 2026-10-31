#!/usr/bin/env bash
# Run my-app in my-namespace (labelled for my-webhook) with two replicas, and a webhook
# Deployment and Service in my-webhook-system.
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
  labels:
    my-webhook: enabled
---
apiVersion: v1
kind: Namespace
metadata:
  name: my-webhook-system
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-webhook
  namespace: my-webhook-system
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-webhook
  template:
    metadata:
      labels:
        app: my-webhook
    spec:
      containers:
        - name: webhook
          # A stand-in: the scenario only needs the Deployment to stop having pods.
          image: ${NGINX_IMAGE}
          ports:
            - containerPort: 8443
---
apiVersion: v1
kind: Service
metadata:
  name: my-webhook
  namespace: my-webhook-system
spec:
  selector:
    app: my-webhook
  ports:
    - port: 443
      targetPort: 8443
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-namespace
spec:
  replicas: 2
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
YAML
kubectl rollout status deployment/my-app -n my-namespace --timeout=180s

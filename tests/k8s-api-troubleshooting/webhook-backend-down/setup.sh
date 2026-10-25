#!/usr/bin/env bash
# Create my-namespace (labelled for my-webhook) and the webhook's own namespace, with a
# Service in front of a webhook Deployment that someone scaled to zero.
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
  replicas: 0
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
          # A stand-in: the scenario only needs the Deployment to have no pods.
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
YAML

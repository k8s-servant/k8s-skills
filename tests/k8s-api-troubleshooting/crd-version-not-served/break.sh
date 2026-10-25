#!/usr/bin/env bash
# Run the deploy Job, which applies a Widget written for v1alpha1. kubectl finds no
# served version for it and the Job fails.
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
  name: my-deploy-manifests
  namespace: my-namespace
data:
  widget.yaml: |
    apiVersion: my-api.example.com/v1alpha1
    kind: Widget
    metadata:
      name: my-widget
      namespace: my-namespace
    spec:
      size: 3
---
apiVersion: batch/v1
kind: Job
metadata:
  name: my-deploy
  namespace: my-namespace
spec:
  backoffLimit: 0
  template:
    spec:
      serviceAccountName: my-deploy
      restartPolicy: Never
      containers:
        - name: deploy
          image: ${KUBECTL_IMAGE}
          args: [apply, -f, /manifests/widget.yaml]
          volumeMounts:
            - name: manifests
              mountPath: /manifests
          resources:
            requests:
              cpu: 10m
              memory: 32Mi
            limits:
              memory: 64Mi
      volumes:
        - name: manifests
          configMap:
            name: my-deploy-manifests
YAML
wait_for --for=condition=Failed job/my-deploy -n my-namespace

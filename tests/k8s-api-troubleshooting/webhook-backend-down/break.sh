#!/usr/bin/env bash
# Register a validating webhook for pods in namespaces labelled my-webhook=enabled, with
# failurePolicy Fail, then deploy my-app there. Its ReplicaSet cannot create a pod,
# because the webhook's Service has no endpoints.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<YAML
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: my-webhook
webhooks:
  - name: validate.my-webhook.example.com
    admissionReviewVersions: [v1]
    sideEffects: None
    failurePolicy: Fail
    timeoutSeconds: 5
    namespaceSelector:
      matchLabels:
        my-webhook: enabled
    rules:
      - apiGroups: [""]
        apiVersions: [v1]
        operations: [CREATE, UPDATE]
        resources: [pods]
    clientConfig:
      service:
        name: my-webhook
        namespace: my-webhook-system
        path: /validate
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
YAML
for _ in $(seq 1 24); do
  if kubectl get events -n my-namespace --field-selector reason=FailedCreate 2>/dev/null \
    | grep -q 'failed calling webhook'; then
    exit 0
  fi
  sleep 5
done
echo "my-app's ReplicaSet never hit the webhook" >&2
exit 1

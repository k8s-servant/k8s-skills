#!/usr/bin/env bash
# Register a validating webhook for pods in namespaces labelled my-webhook=enabled, with
# failurePolicy Fail, and scale its backend to zero. my-app's running pods are fine, but
# any pod recreated there (as a drain does) is refused.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
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
YAML
kubectl scale deployment my-webhook -n my-webhook-system --replicas=0
kubectl wait --for=delete pod -l app=my-webhook -n my-webhook-system --timeout=120s

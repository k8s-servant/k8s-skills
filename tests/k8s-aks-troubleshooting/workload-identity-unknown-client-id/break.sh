#!/usr/bin/env bash
# my-app uses workload identity, but its ServiceAccount names a client ID that belongs to
# no identity. The app exchanges its token at Microsoft Entra ID every 30 seconds and logs
# the error it gets back. No Azure resource is created.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

image="${K8S_SKILLS_TEST_IMAGE:-curlimages/curl:8.10.1}"
manifest="$(cat <<'YAML'
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app
  namespace: my-namespace
  annotations:
    azure.workload.identity/client-id: 11111111-2222-3333-4444-555555555555
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
        azure.workload.identity/use: "true"
    spec:
      serviceAccountName: my-app
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
        - name: app
          image: TEST_IMAGE
          command: ["sh", "-c"]
          args:
            - |
              while true; do
                curl -s -X POST "${AZURE_AUTHORITY_HOST}${AZURE_TENANT_ID}/oauth2/v2.0/token" \
                  -d client_id="$AZURE_CLIENT_ID" -d grant_type=client_credentials \
                  -d scope=https://management.azure.com/.default \
                  -d client_assertion_type=urn:ietf:params:oauth:client-assertion-type:jwt-bearer \
                  --data-urlencode client_assertion@"$AZURE_FEDERATED_TOKEN_FILE" > /tmp/reply
                echo "token request failed: $(sed -n 's/.*"error_description":"\([^"]*\)".*/\1/p' /tmp/reply | cut -d'\' -f1)"
                sleep 30
              done
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 64Mi
YAML
)"
kubectl apply -f - <<<"${manifest//TEST_IMAGE/$image}"
wait_for --for=condition=Available deployment/my-app -n my-namespace

for _ in $(seq 1 24); do
  if kubectl logs deployment/my-app -n my-namespace 2>/dev/null | grep -q AADSTS; then
    exit 0
  fi
  sleep 5
done
echo "my-app logged no AADSTS error after 2 minutes" >&2
exit 1

#!/usr/bin/env bash
# Deploy my-app with a readiness probe on a path the app does not serve (/healthz;
# nginx answers 404), so the pod runs but never becomes Ready and the Service gets no
# endpoints. Then wait until the probe has failed and been reported.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<YAML
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
          image: ${NGINX_IMAGE}  # nginx:1.29-alpine, pinned in tests/versions.env
          ports:
            - containerPort: 80
          readinessProbe:
            httpGet:
              path: /healthz
              port: 80
            periodSeconds: 5
            failureThreshold: 3
YAML
for _ in $(seq 1 60); do
  if kubectl -n my-namespace get events --field-selector reason=Unhealthy -o name | grep -q .; then
    exit 0
  fi
  sleep 3
done
echo "the readiness probe never reported a failure" >&2
exit 1

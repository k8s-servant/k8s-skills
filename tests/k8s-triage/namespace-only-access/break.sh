#!/usr/bin/env bash
# Run a my-app in my-namespace that exits with an error on every start, and a healthy
# my-web in my-other-namespace that the agent cannot see, then wait for the restarts.
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
  name: my-web
  namespace: my-other-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-web
  template:
    metadata:
      labels:
        app: my-web
    spec:
      containers:
        - name: app
          image: ${NGINX_IMAGE}
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 64Mi
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
          # Stand-in for an app that cannot find its config file and exits.
          command: ["sh", "-c", "echo starting my-app; echo config file /etc/my-app/app.conf not found; exit 1"]
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 64Mi
YAML
for _ in $(seq 1 60); do
  restarts="$(kubectl -n my-namespace get pods -l app=my-app \
    -o jsonpath='{.items[*].status.containerStatuses[*].restartCount}')"
  if [[ "${restarts:-0}" -ge 2 ]]; then
    exit 0
  fi
  sleep 3
done
echo "my-app did not restart twice" >&2
exit 1

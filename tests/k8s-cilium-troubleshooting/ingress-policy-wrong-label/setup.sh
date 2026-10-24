#!/usr/bin/env bash
# Run my-app (nginx) and a client, my-web, in my-namespace. Needs a cluster with Cilium
# as its CNI: tests/cluster.sh up --cni cilium.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

if ! kubectl get daemonset cilium -n kube-system >/dev/null 2>&1; then
  echo "this scenario needs Cilium: tests/cluster.sh up --cni cilium" >&2
  exit 1
fi
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
            - name: http
              containerPort: 80
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
      targetPort: http
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-web
  namespace: my-namespace
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
        - name: web
          image: ${BUSYBOX_IMAGE}
          # Calls my-app every 5 seconds and logs each result, as a real client would.
          command:
            - sh
            - -c
            - |
              while true; do
                if out=\$(wget -qO /dev/null -T 2 http://my-app.my-namespace/ 2>&1); then
                  echo "\$(date) GET http://my-app.my-namespace/ ok"
                else
                  echo "\$(date) GET http://my-app.my-namespace/ failed: \$out"
                fi
                sleep 5
              done
YAML
kubectl rollout status deployment/my-app -n my-namespace --timeout=180s
kubectl rollout status deployment/my-web -n my-namespace --timeout=180s

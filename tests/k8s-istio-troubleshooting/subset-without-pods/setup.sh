#!/usr/bin/env bash
# Install Istio (pinned in versions.env; needs helm) and run my-app (nginx, version v1)
# in my-namespace, which has sidecar injection on, and a client, my-web.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

"$REPO_ROOT/tests/addon.sh" istio
kubectl apply -f - <<YAML
apiVersion: v1
kind: Namespace
metadata:
  name: my-namespace
  labels:
    istio-injection: enabled
---
apiVersion: v1
kind: Namespace
metadata:
  name: my-other-namespace
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app
  namespace: my-namespace
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
        version: v1
    spec:
      serviceAccountName: my-app
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
    - name: http
      port: 80
      targetPort: http
---
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-web
  namespace: my-namespace
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
      serviceAccountName: my-web
      containers:
        - name: web
          image: ${BUSYBOX_IMAGE}
          # Calls my-app every 5 seconds and logs each result, as a real client would.
          command:
            - sh
            - -c
            - |
              while true; do
                if out=\$(wget -qO /dev/null -T 3 http://my-app.my-namespace/ 2>&1); then
                  echo "\$(date) GET http://my-app.my-namespace/ ok"
                else
                  echo "\$(date) GET http://my-app.my-namespace/ failed: \$out"
                fi
                sleep 5
              done
YAML
kubectl rollout status deployment/my-app -n my-namespace --timeout=240s
kubectl rollout status deployment/my-web -n my-namespace --timeout=240s

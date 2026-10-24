#!/usr/bin/env bash
# Run my-app and a client, my-web, in another namespace. A NetworkPolicy in my-namespace
# allows ingress only from pods in the same namespace, so my-web is blocked. Needs a
# cluster with a policy-enforcing CNI: tests/cluster.sh up --cni calico.
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
          ports:
            - name: http
              containerPort: 80
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 64Mi
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
      targetPort: 80
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-same-namespace
  namespace: my-namespace
spec:
  podSelector: {}
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector: {}
---
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
        - name: web
          image: ${BUSYBOX_IMAGE}
          # Calls my-app every 5 seconds and logs each result, as a real client would.
          command:
            - sh
            - -c
            - |
              while true; do
                if wget -qO /dev/null -T 2 http://my-app.my-namespace/; then
                  echo "\$(date) GET http://my-app.my-namespace/ ok"
                else
                  echo "\$(date) GET http://my-app.my-namespace/ failed"
                fi
                sleep 5
              done
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 32Mi
YAML
kubectl -n my-namespace rollout status deployment/my-app --timeout=120s
kubectl -n my-other-namespace rollout status deployment/my-web --timeout=120s
for _ in $(seq 1 24); do
  if kubectl logs -n my-other-namespace deployment/my-web | grep -q failed; then
    exit 0
  fi
  sleep 5
done
echo "my-web never failed to reach my-app" >&2
exit 1

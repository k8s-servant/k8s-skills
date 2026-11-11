#!/usr/bin/env bash
# my-app drifted: a privileged container with the node's /var/log mounted, running as
# root, and its ServiceAccount bound to cluster-admin.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
# shellcheck source=../review.sh disable=SC1091
source "$(dirname "$0")/../review.sh"
require_test_cluster

kubectl apply -f - <<YAML
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app
  namespace: my-namespace
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: my-app-admin
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: cluster-admin
subjects:
  - kind: ServiceAccount
    name: my-app
    namespace: my-namespace
---
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
      serviceAccountName: my-app
      containers:
        - name: app
          image: ${NGINX_IMAGE}
          readinessProbe:
            httpGet:
              path: /
              port: 80
          resources:
            requests:
              cpu: 10m
              memory: 32Mi
          securityContext:
            privileged: true
          volumeMounts:
            - name: logs
              mountPath: /host/var/log
      volumes:
        - name: logs
          hostPath:
            path: /var/log
YAML
kubectl rollout status deployment/my-app -n my-namespace --timeout=180s

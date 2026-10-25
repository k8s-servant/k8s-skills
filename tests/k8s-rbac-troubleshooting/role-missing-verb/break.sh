#!/usr/bin/env bash
# Run my-app, which watches ConfigMaps in its namespace. Its Role grants only get, so
# the list that starts the watch is refused.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<YAML

apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: my-app-config-reader
  namespace: my-namespace
rules:
  - apiGroups: [""]
    resources: [configmaps]
    verbs: [get]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: my-app-config-reader
  namespace: my-namespace
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: my-app-config-reader
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
  replicas: 1
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
          image: ${KUBECTL_IMAGE}
          # Watches the API the way a small controller does; a refused request ends it.
          args: [get, configmaps, --namespace, my-namespace, --watch]
          resources:
            requests:
              cpu: 10m
              memory: 32Mi
            limits:
              memory: 64Mi
YAML
for _ in $(seq 1 24); do
  logs="$(kubectl logs -n my-namespace deployment/my-app 2>/dev/null || true)"
  if [[ "$logs" == *Forbidden* ]]; then
    exit 0
  fi
  sleep 5
done
echo "my-app was never refused" >&2
exit 1

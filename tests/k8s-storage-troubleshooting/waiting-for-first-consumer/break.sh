#!/usr/bin/env bash
# Create my-app's PVC ahead of the release, with the Deployment still scaled to zero.
# The default StorageClass binds only when a pod uses the claim, so the PVC is Pending,
# and nothing is wrong.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<YAML
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-data
  namespace: my-namespace
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: my-namespace
spec:
  replicas: 0
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
          command: ["sh", "-c", "date >> /data/started; sleep 3600"]
          volumeMounts:
            - name: data
              mountPath: /data
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 32Mi
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: my-data
YAML
for _ in $(seq 1 24); do
  if kubectl get events -n my-namespace --field-selector reason=WaitForFirstConsumer -o name | grep -q .; then
    exit 0
  fi
  sleep 5
done
echo "no WaitForFirstConsumer event for my-data" >&2
exit 1

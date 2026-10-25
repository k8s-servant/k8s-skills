#!/usr/bin/env bash
# A Deployment whose PVC asks Azure Disk for 40 TiB, more than one disk can hold. Azure
# rejects the disk, so nothing is created.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

image="${K8S_SKILLS_TEST_IMAGE:-curlimages/curl:8.10.1}"
kubectl apply -f - <<YAML
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-data
  namespace: my-namespace
spec:
  accessModes: [ReadWriteOnce]
  storageClassName: managed-csi
  resources:
    requests:
      storage: 40Ti
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-db
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-db
  template:
    metadata:
      labels:
        app: my-db
    spec:
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
      containers:
        - name: db
          image: ${image}
          command: ["sleep", "86400"]
          volumeMounts:
            - name: data
              mountPath: /data
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 64Mi
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: my-data
YAML

for _ in $(seq 1 36); do
  if kubectl events -n my-namespace --for pvc/my-data 2>/dev/null | grep -q ProvisioningFailed; then
    exit 0
  fi
  sleep 5
done
echo "no ProvisioningFailed event for my-data after 3 minutes" >&2
exit 1

#!/usr/bin/env bash
# Leftovers in my-namespace: a PVC no pod mounts, a Service whose selector matches no
# pod, and a Job that failed.
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
kind: PersistentVolumeClaim
metadata:
  name: my-data
  namespace: my-namespace
spec:
  accessModes: [ReadWriteOnce]
  resources:
    requests:
      storage: 1Gi
---
apiVersion: v1
kind: Service
metadata:
  name: my-app
  namespace: my-namespace
spec:
  selector:
    app: my-old-app
  ports:
    - port: 9898
---
apiVersion: batch/v1
kind: Job
metadata:
  name: my-migration
  namespace: my-namespace
spec:
  backoffLimit: 0
  template:
    spec:
      restartPolicy: Never
      securityContext: ${RESTRICTED_POD}
      containers:
        - name: migrate
          image: ${BUSYBOX_IMAGE}
          command: ["sh", "-c", "echo 'migration failed: table my_table not found'; exit 1"]
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
          securityContext: ${RESTRICTED_CONTAINER}
YAML
wait_for --for=condition=Failed job/my-migration -n my-namespace

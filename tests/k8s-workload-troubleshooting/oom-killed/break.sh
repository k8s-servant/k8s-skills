#!/usr/bin/env bash
# Deploy my-app with a memory limit (32Mi) far below what it uses at start-up (it
# buffers about 100 MiB), so the kernel kills it every time, then wait until the
# container has been OOM killed at least once.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
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
          image: busybox:1.37
          # Stand-in for an application that loads a large cache at start-up:
          # busybox tail keeps the whole newline-free input in memory.
          command: ["sh", "-c", "echo loading cache; head -c 100m /dev/zero | tail; echo ready; sleep 3600"]
          resources:
            requests:
              memory: 32Mi
              cpu: 10m
            limits:
              memory: 32Mi
YAML
for _ in $(seq 1 60); do
  reason="$(kubectl -n my-namespace get pods -l app=my-app \
    -o jsonpath='{.items[*].status.containerStatuses[*].lastState.terminated.reason}')"
  if [[ "$reason" == *OOMKilled* ]]; then
    exit 0
  fi
  sleep 3
done
echo "my-app was never OOM killed" >&2
exit 1

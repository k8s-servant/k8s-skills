#!/usr/bin/env bash
# Run Loki with auth_enabled: true (multi-tenant) and my-app-logger, which pushes a line
# every 10 seconds without an X-Scope-OrgID header.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<YAML
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-loki
  namespace: my-namespace
data:
  # Monolithic Loki on the local filesystem, as in the image's own config.
  config.yaml: |
    auth_enabled: true
    server:
      http_listen_port: 3100
    common:
      instance_addr: 127.0.0.1
      path_prefix: /loki
      storage:
        filesystem:
          chunks_directory: /loki/chunks
          rules_directory: /loki/rules
      replication_factor: 1
      ring:
        kvstore:
          store: inmemory
    schema_config:
      configs:
        - from: 2020-10-24
          store: tsdb
          object_store: filesystem
          schema: v13
          index:
            prefix: index_
            period: 24h
    analytics:
      reporting_enabled: false
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-loki
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-loki
  template:
    metadata:
      labels:
        app: my-loki
    spec:
      containers:
        - name: loki
          image: ${LOKI_IMAGE}
          args: ["-config.file=/etc/loki/config.yaml"]
          ports:
            - name: http-metrics
              containerPort: 3100
          readinessProbe:
            httpGet:
              path: /ready
              port: http-metrics
          volumeMounts:
            - name: config
              mountPath: /etc/loki
            - name: data
              mountPath: /loki
          resources:
            requests:
              cpu: 50m
              memory: 128Mi
            limits:
              memory: 512Mi
      volumes:
        - name: config
          configMap:
            name: my-loki
        - name: data
          emptyDir: {}
---
apiVersion: v1
kind: Service
metadata:
  name: my-loki
  namespace: my-namespace
spec:
  selector:
    app: my-loki
  ports:
    - name: http-metrics
      port: 3100
      targetPort: http-metrics
YAML
kubectl -n my-namespace rollout status deployment/my-loki --timeout=180s

kubectl apply -f - <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app-logger
  namespace: my-namespace
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-app-logger
  template:
    metadata:
      labels:
        app: my-app-logger
    spec:
      containers:
        - name: logger
          image: ${BUSYBOX_IMAGE}
          # Pushes one log line to Loki every 10 seconds and logs the result, as a
          # small log shipper would.
          command:
            - sh
            - -c
            - |
              while true; do
                body="{\\"streams\\":[{\\"stream\\":{\\"app\\":\\"my-app\\"},\\"values\\":[[\\"\$(date +%s)000000000\\",\\"order processed\\"]]}]}"
                if wget -q -O /dev/null --header 'Content-Type: application/json' --post-data "\$body" http://my-loki:3100/loki/api/v1/push; then
                  echo "\$(date) push to http://my-loki:3100 ok"
                else
                  echo "\$(date) push to http://my-loki:3100 failed"
                fi
                sleep 10
              done
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 32Mi
YAML
kubectl -n my-namespace rollout status deployment/my-app-logger --timeout=120s
for _ in $(seq 1 24); do
  logs="$(kubectl logs -n my-namespace deployment/my-app-logger 2>/dev/null || true)"
  if [[ "$logs" == *"401 Unauthorized"* ]]; then
    exit 0
  fi
  sleep 5
done
echo "my-app-logger never got 401 Unauthorized" >&2
exit 1

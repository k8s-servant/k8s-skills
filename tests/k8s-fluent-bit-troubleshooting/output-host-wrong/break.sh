#!/usr/bin/env bash
# Run Fluent Bit as a DaemonSet that tails my-app and sends to the receiver. The
# output's Host is misspelled (log-receivr), a name that does not resolve.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<YAML
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-fluent-bit
  namespace: my-namespace
---
# The kubernetes filter reads pod and namespace metadata, as the Helm chart's role does.
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: my-fluent-bit
rules:
  - apiGroups: [""]
    resources: [namespaces, pods]
    verbs: [get, list, watch]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: my-fluent-bit
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: my-fluent-bit
subjects:
  - kind: ServiceAccount
    name: my-fluent-bit
    namespace: my-namespace
---
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-fluent-bit
  namespace: my-namespace
data:
  # Laid out like the Helm chart's classic config, tailing my-namespace's containers.
  fluent-bit.conf: |
    [SERVICE]
        Daemon Off
        Flush 1
        Log_Level info
        HTTP_Server On
        HTTP_Listen 0.0.0.0
        HTTP_Port 2020
        Health_Check On

    [INPUT]
        Name tail
        Path /var/log/containers/my-app-*_my-namespace_*.log
        multiline.parser docker, cri
        Tag kube.*
        Mem_Buf_Limit 5MB
        Skip_Long_Lines On

    [FILTER]
        Name kubernetes
        Match kube.*
        Merge_Log On
        Keep_Log Off

    [OUTPUT]
        Name http
        Match kube.*
        Host log-receivr.my-namespace.svc
        Port 9880
        Format json
---
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: my-fluent-bit
  namespace: my-namespace
  labels:
    app.kubernetes.io/name: fluent-bit
    app.kubernetes.io/instance: my-fluent-bit
spec:
  selector:
    matchLabels:
      app.kubernetes.io/name: fluent-bit
      app.kubernetes.io/instance: my-fluent-bit
  template:
    metadata:
      labels:
        app.kubernetes.io/name: fluent-bit
        app.kubernetes.io/instance: my-fluent-bit
    spec:
      serviceAccountName: my-fluent-bit
      containers:
        - name: fluent-bit
          image: ${FLUENT_BIT_IMAGE}
          args: ["--workdir=/fluent-bit/etc", "--config=/fluent-bit/etc/conf/fluent-bit.conf"]
          ports:
            - name: http
              containerPort: 2020
          volumeMounts:
            - name: config
              mountPath: /fluent-bit/etc/conf
            - name: varlog
              mountPath: /var/log
              readOnly: true
          resources:
            requests:
              cpu: 10m
              memory: 32Mi
            limits:
              memory: 128Mi
      volumes:
        - name: config
          configMap:
            name: my-fluent-bit
        - name: varlog
          hostPath:
            path: /var/log
YAML
kubectl -n my-namespace rollout status daemonset/my-fluent-bit --timeout=120s
for _ in $(seq 1 36); do
  logs="$(kubectl logs -n my-namespace daemonset/my-fluent-bit 2>/dev/null || true)"
  if [[ "$logs" == *"failed to flush chunk"* ]]; then
    exit 0
  fi
  sleep 5
done
echo "Fluent Bit never logged: failed to flush chunk" >&2
exit 1

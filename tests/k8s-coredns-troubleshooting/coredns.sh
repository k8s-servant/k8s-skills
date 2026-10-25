#!/usr/bin/env bash
# Shared helpers for the CoreDNS scenarios. Source this file after lib.sh, never run it.
# The scenarios change the cluster's Corefile, so setup saves the original outside the
# cluster (in the git-ignored .kube/ folder, where the agent cannot read it) and cleanup
# puts it back.

COREDNS_BACKUP="$REPO_ROOT/.kube/coredns-Corefile.orig"

# Save the running Corefile once; a second setup keeps the first, unbroken copy.
coredns_save() {
  if [[ ! -s "$COREDNS_BACKUP" ]]; then
    kubectl get configmap coredns -n kube-system -o jsonpath='{.data.Corefile}' > "$COREDNS_BACKUP"
  fi
}

# Replace the Corefile with the file in $1.
coredns_apply() {
  kubectl create configmap coredns -n kube-system --from-file=Corefile="$1" \
    --dry-run=client -o yaml | kubectl apply -f -
}

# Wait until every CoreDNS pod has logged a line matching $1 (the kubelet syncs the
# ConfigMap within about a minute, and the reload plugin checks every 30 s or so).
coredns_wait_log() {
  local pods pod done_all
  for _ in $(seq 1 36); do
    done_all=true
    pods="$(kubectl get pods -n kube-system -l k8s-app=kube-dns -o name)"
    for pod in $pods; do
      if ! kubectl logs -n kube-system "$pod" 2>/dev/null | grep -qE "$1"; then
        done_all=false
      fi
    done
    if [[ "$done_all" == true ]]; then
      return 0
    fi
    sleep 5
  done
  echo "CoreDNS never logged: $1" >&2
  return 1
}

# Put the saved Corefile back and restart CoreDNS, so no pod keeps a broken one.
coredns_restore() {
  if [[ -s "$COREDNS_BACKUP" ]]; then
    coredns_apply "$COREDNS_BACKUP"
    kubectl rollout restart deployment/coredns -n kube-system
    kubectl rollout status deployment/coredns -n kube-system --timeout=180s
    rm -f "$COREDNS_BACKUP"
  fi
}

# The client: looks names up every 10 s and logs what it got.
coredns_client() {
  local names="$1"
  kubectl apply -f - <<YAML
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
      containers:
        - name: web
          image: ${BUSYBOX_IMAGE}
          command:
            - sh
            - -c
            - |
              while true; do
                for name in ${names}; do
                  out="\$(nslookup "\$name" 2>&1)"
                  if echo "\$out" | grep -q '^Name:'; then
                    echo "ok \$name"
                  else
                    echo "FAILED \$name: \$(echo "\$out" | grep -E "can't find|timed out|no servers" | head -n 1)"
                  fi
                done
                sleep 10
              done
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              memory: 32Mi
YAML
  wait_for --for=condition=Available deployment/my-web -n my-namespace
}

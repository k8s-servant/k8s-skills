#!/usr/bin/env bash
# A CA Issuer points at a key pair that was never created, so it is not Ready and the
# Certificate for my-app is never issued.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: cert-manager.io/v1
kind: Issuer
metadata:
  name: my-ca-issuer
  namespace: my-namespace
spec:
  ca:
    secretName: my-ca-key-pair
---
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: my-app-tls
  namespace: my-namespace
spec:
  secretName: my-app-tls
  dnsNames:
    - my-app.example.com
  issuerRef:
    name: my-ca-issuer
YAML
wait_for --for=condition=Ready=false issuer/my-ca-issuer -n my-namespace
wait_for --for=condition=Ready=false certificate/my-app-tls -n my-namespace

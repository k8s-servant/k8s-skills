#!/usr/bin/env bash
# A working self-signed ClusterIssuer exists, but the Certificate's issuerRef leaves out
# `kind: ClusterIssuer`. The kind defaults to Issuer, so cert-manager looks for an
# Issuer of that name in my-namespace and never issues the certificate.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl apply -f - <<'YAML'
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: my-cluster-issuer
spec:
  selfSigned: {}
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
    name: my-cluster-issuer
YAML
wait_for --for=condition=Ready clusterissuer/my-cluster-issuer
wait_for --for=condition=Ready=false certificate/my-app-tls -n my-namespace

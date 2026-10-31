#!/usr/bin/env bash
# Someone started a pod by hand (my-debug) with no controller. A node drain refuses it
# without --force, and with --force the pod is deleted and never comes back.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
require_test_cluster

kubectl apply -f - <<YAML
apiVersion: v1
kind: Pod
metadata:
  name: my-debug
  namespace: my-namespace
spec:
  containers:
    - name: debug
      image: ${NGINX_IMAGE}
YAML
wait_for --for=condition=Ready pod/my-debug -n my-namespace

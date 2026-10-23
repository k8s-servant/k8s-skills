#!/usr/bin/env bash
# Roll out a "new version" whose image tag does not exist (a typo in the tag), then
# wait until the new pod reports the pull failure.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
require_test_cluster

kubectl -n my-namespace set image deployment/my-app app=nginx:1.299-alpine
for _ in $(seq 1 60); do
  reasons="$(kubectl -n my-namespace get pods -l app=my-app \
    -o jsonpath='{.items[*].status.containerStatuses[*].state.waiting.reason}')"
  if [[ "$reasons" == *ImagePullBackOff* || "$reasons" == *ErrImagePull* ]]; then
    exit 0
  fi
  sleep 3
done
echo "the new pod never reported an image pull failure" >&2
exit 1

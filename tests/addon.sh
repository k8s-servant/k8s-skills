#!/usr/bin/env bash
# Install a pinned third-party add-on into the kind test cluster, for the ecosystem
# skills' scenarios. The manifest is checked against a pinned checksum before it is
# applied. Running it again re-applies the same version, so scenarios can call it in
# their setup.sh.
#
# Usage: tests/addon.sh <name>
# Names: cert-manager
set -euo pipefail
# shellcheck source-path=SCRIPTDIR

# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"
# shellcheck source=versions.env disable=SC1091
source "$(dirname "${BASH_SOURCE[0]}")/versions.env"

usage() {
  echo "usage: tests/addon.sh cert-manager" >&2
  exit 64
}

[[ $# -eq 1 ]] || usage
case "$1" in
  cert-manager)
    url="https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"
    sum="$CERT_MANAGER_MANIFEST_SHA256"
    namespace="cert-manager"
    ;;
  *) usage ;;
esac

require_test_cluster

manifest=""
trap 'rm -f "$manifest"' EXIT
manifest="$(mktemp)"
fetch_verified "$url" "$sum" "$manifest"
kubectl apply -f "$manifest" >&2
kubectl wait --for=condition=Available deployment --all -n "$namespace" --timeout=300s >&2

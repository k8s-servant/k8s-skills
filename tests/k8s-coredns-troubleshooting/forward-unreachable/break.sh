#!/usr/bin/env bash
# Point CoreDNS's upstream at 192.0.2.53 (TEST-NET-1, nothing answers there). Service
# names still resolve; every other name times out. my-web looks up both: my-app's
# Service name and k8s-skills-test-control-plane, a host the node's resolver knows.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
# shellcheck source=../coredns.sh disable=SC1091
source "$(dirname "$0")/../coredns.sh"
require_test_cluster

coredns_client "my-app.my-namespace.svc.cluster.local k8s-skills-test-control-plane."
corefile="$(mktemp)"
trap 'rm -f "$corefile"' EXIT
cat > "$corefile" <<'COREFILE'
.:53 {
    errors
    health {
       lameduck 5s
    }
    ready
    kubernetes cluster.local in-addr.arpa ip6.arpa {
       pods insecure
       fallthrough in-addr.arpa ip6.arpa
       ttl 30
    }
    prometheus :9153
    forward . 192.0.2.53 {
       max_concurrent 1000
    }
    cache 30 {
       disable success cluster.local
       disable denial cluster.local
    }
    loop
    reload
    loadbalance
}
COREFILE
coredns_apply "$corefile"
coredns_wait_log 'i/o timeout'

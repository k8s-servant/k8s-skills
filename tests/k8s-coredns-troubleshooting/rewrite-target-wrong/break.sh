#!/usr/bin/env bash
# Add a rewrite so my-app.example.com answers with my-app's Service, but with a typo in
# the target (my-ap). my-app.example.com gets NXDOMAIN, and CoreDNS logs nothing.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
# shellcheck source=../coredns.sh disable=SC1091
source "$(dirname "$0")/../coredns.sh"
require_test_cluster

coredns_client "my-app.my-namespace.svc.cluster.local my-app.example.com"
corefile="$(mktemp)"
trap 'rm -f "$corefile"' EXIT
cat > "$corefile" <<'COREFILE'
.:53 {
    errors
    health {
       lameduck 5s
    }
    ready
    rewrite name my-app.example.com my-ap.my-namespace.svc.cluster.local
    kubernetes cluster.local in-addr.arpa ip6.arpa {
       pods insecure
       fallthrough in-addr.arpa ip6.arpa
       ttl 30
    }
    prometheus :9153
    forward . /etc/resolv.conf {
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
coredns_wait_log 'Reloading complete'
for _ in $(seq 1 24); do
  if kubectl logs -n my-namespace deployment/my-web --tail=4 | grep -q 'FAILED my-app.example.com'; then
    exit 0
  fi
  sleep 5
done
echo "my-web never failed to resolve my-app.example.com" >&2
exit 1

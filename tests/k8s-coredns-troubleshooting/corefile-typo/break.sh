#!/usr/bin/env bash
# Edit the Corefile with a typo on its last plugin line (loadbalanse). Running CoreDNS
# pods refuse the reload and keep the old configuration; then restart CoreDNS, as an
# operator would to "pick up" the edit. The new pods crash; one old pod keeps serving.
set -euo pipefail
# shellcheck source=../../lib.sh disable=SC1091
source "$(dirname "$0")/../../lib.sh"
# shellcheck source=../../versions.env disable=SC1091
source "$(dirname "$0")/../../versions.env"
# shellcheck source=../coredns.sh disable=SC1091
source "$(dirname "$0")/../coredns.sh"
require_test_cluster

coredns_client "my-app.my-namespace.svc.cluster.local"
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
    forward . /etc/resolv.conf {
       max_concurrent 1000
    }
    cache 30 {
       disable success cluster.local
       disable denial cluster.local
    }
    loop
    reload
    loadbalanse
}
COREFILE
coredns_apply "$corefile"
coredns_wait_log 'reload failed'
kubectl rollout restart deployment/coredns -n kube-system
for _ in $(seq 1 36); do
  if kubectl get pods -n kube-system -l k8s-app=kube-dns | grep -q CrashLoopBackOff; then
    exit 0
  fi
  sleep 5
done
echo "no CoreDNS pod crashed" >&2
exit 1

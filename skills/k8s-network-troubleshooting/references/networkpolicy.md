# NetworkPolicy blocking traffic

A pod accepts all traffic until a NetworkPolicy selects it for a direction (`Ingress`,
`Egress`). From then on, only traffic some policy allows gets through in that direction.
Policies add up and never conflict. A connection needs both the client's egress and the
target's ingress to allow it. Policies only work with a network plugin that enforces
them; without one, they are accepted and do nothing.

## Investigate

```bash
kubectl get networkpolicy -A
kubectl describe networkpolicy -n my-namespace
kubectl get networkpolicy -n my-namespace -o yaml
kubectl describe networkpolicy -n my-other-namespace
kubectl get namespace my-other-namespace --show-labels
kubectl get pods -n my-other-namespace -l app=my-web --show-labels
kubectl get pods -n kube-system -o wide
```

The last command shows which network plugin runs (Calico, Cilium, ...), and so whether
policies are enforced.

## Read the results

- **A policy with `podSelector: {}`** selects every pod in its namespace.
- **`from` with only a `podSelector`** allows pods in the policy's own namespace only.
  Pods from another namespace need a `namespaceSelector`; every namespace has the label
  `kubernetes.io/metadata.name: <name>`.
- **`namespaceSelector` and `podSelector` in the same `from` entry** mean both must
  match; in two separate entries, either one.
- **Ports**: a rule with `ports` allows only those ports (the pod's port, not the
  Service's `port`, when they differ).
- **Egress on the client**: if a policy isolates the client for egress, it also needs to
  allow DNS (to the cluster's DNS pods) and the target's port.
- **Time-outs, not refused connections**, are the usual sign of a dropped packet.
- An ingress-isolated pod still accepts connections from its own node.

## Proposed fix

Allow the client explicitly, with a new policy next to the existing ones (policies add
up, so this opens only what it names). Creating a policy changes who can reach the
workload, so a human reviews and applies it, best through the source the policies are
deployed from:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl apply -f - <<'YAML'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-my-web
  namespace: my-namespace
spec:
  podSelector:
    matchLabels:
      app: my-app
  policyTypes:
    - Ingress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: my-other-namespace
          podSelector:
            matchLabels:
              app: my-web
      ports:
        - port: 80
YAML
# Undo: kubectl delete networkpolicy allow-my-web -n my-namespace
```

Do not propose deleting an existing policy to make traffic flow: it may protect other
workloads. Ask the user what it is for first.

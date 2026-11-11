#!/usr/bin/env bash
# Shared helpers for the cluster review scenarios. Source this file after lib.sh and
# versions.env, never run it.
#
# Every scenario also runs a clean app, my-decoy, in its own namespace: two replicas,
# readiness probe, requests, restricted securityContext, a PDB that allows one
# disruption, and NetworkPolicies. Any finding about my-decoy is a wrong answer, so the
# scenarios check that the review stays quiet as well as what it finds.

# The pod and container securityContext the restricted Pod Security level asks for.
RESTRICTED_POD='{"runAsNonRoot": true, "runAsUser": 10001, "seccompProfile": {"type": "RuntimeDefault"}}'
RESTRICTED_CONTAINER='{"allowPrivilegeEscalation": false, "capabilities": {"drop": ["ALL"]}}'

# Create namespace $1 with restricted Pod Security enforced, a default-deny ingress
# NetworkPolicy and one allowing ingress to port 9898 (podinfo).
review_clean_namespace() {
  kubectl apply -f - <<YAML
apiVersion: v1
kind: Namespace
metadata:
  name: $1
  labels:
    pod-security.kubernetes.io/enforce: restricted
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: $1
spec:
  podSelector: {}
  policyTypes: [Ingress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-http
  namespace: $1
spec:
  podSelector: {}
  policyTypes: [Ingress]
  ingress:
    - ports:
        - port: 9898
YAML
}

# Run my-decoy in its own clean namespace and wait until it is ready.
review_decoy() {
  review_clean_namespace my-decoy
  kubectl apply -f - <<YAML
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-decoy
  namespace: my-decoy
spec:
  replicas: 2
  selector:
    matchLabels:
      app: my-decoy
  template:
    metadata:
      labels:
        app: my-decoy
    spec:
      securityContext: ${RESTRICTED_POD}
      containers:
        - name: app
          image: ${PODINFO_IMAGE}
          ports:
            - containerPort: 9898
          readinessProbe:
            httpGet:
              path: /readyz
              port: 9898
          resources:
            requests:
              cpu: 10m
              memory: 32Mi
          securityContext: ${RESTRICTED_CONTAINER}
---
apiVersion: v1
kind: Service
metadata:
  name: my-decoy
  namespace: my-decoy
spec:
  selector:
    app: my-decoy
  ports:
    - port: 9898
---
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: my-decoy
  namespace: my-decoy
spec:
  maxUnavailable: 1
  selector:
    matchLabels:
      app: my-decoy
YAML
  kubectl rollout status deployment/my-decoy -n my-decoy --timeout=180s
}

# Delete the scenario namespaces.
review_cleanup() {
  kubectl delete namespace my-namespace my-decoy --ignore-not-found --wait=true
}

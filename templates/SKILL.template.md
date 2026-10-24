---
name: k8s-SUBJECT-JOB
description: >-
  Use when SYMPTOMS THAT SHOULD TRIGGER THIS SKILL. Name the error messages, statuses and
  words a user would say. Say that it reads first and asks before changing anything. At
  most 1024 characters.
license: Apache-2.0
metadata:
  verified-with: "kubernetes 1.37"
  verified-on: "YYYY-MM-DD"
---

# Title of the skill

One paragraph: what this skill finds out. **Read first, ask before changing.** Run the
investigation commands freely. Run a command under an "Ask first" line only after the user
approves it, and if you are not allowed to run it, give it to the user. Never run a
"Proposed fix"; hand it to the user. Commands use placeholders (`my-namespace`, `my-app`);
replace them with the real names. Never read Secrets.

## When to use

- The symptoms that mean this skill applies.

Hand-offs, by skill name. If the other skill is not installed, keep going here and tell the
user which skill would help:

- When the evidence points elsewhere: `k8s-OTHER-troubleshooting`.

## Investigate

Work through the steps in order. Stop when you have the cause and its evidence.

**1. First step, and why.**

```bash
kubectl get pods -n my-namespace -o wide
```

## Read the results

What each finding means and which cause it points to.

## Proposed fix

Show each fix to the user first: name what it changes, and give an undo. A reversible fix
goes under "Ask first": run it only after the user says yes.

> Ask first: the agent runs this only after the user approves it.

```bash
kubectl set resources deployment/my-app -c app --limits=memory=256Mi -n my-namespace
# Undo: kubectl set resources deployment/my-app -c app --limits=memory=32Mi -n my-namespace
```

A destructive or hard-to-undo fix is never run by the agent. Say why, and hand it over:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl delete pod my-pod -n my-namespace
# Undo: none needed if the pod is managed by a controller, which recreates it
```

## Sources

Checked against the Kubernetes 1.37 documentation:

- [Page title](https://kubernetes.io/docs/): what you took from it.

---
name: k8s-SUBJECT-JOB
description: >-
  Use when SYMPTOMS THAT SHOULD TRIGGER THIS SKILL. Name the error messages, statuses and
  words a user would say. Say it is read-only. At most 1024 characters.
license: Apache-2.0
metadata:
  verified-with: "kubernetes 1.37"
  verified-on: "YYYY-MM-DD"
---

# Title of the skill

One paragraph: what this skill finds out. **You only read.** Every fix goes to the user as
a proposal for a human to review and run. Commands use placeholders (`my-namespace`,
`my-app`); replace them with the real names. Never read Secrets.

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

Show each fix to the user; do not run it. Name what it changes, and give an undo.

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl set resources deployment/my-app -c app --limits=memory=256Mi -n my-namespace
# Undo: kubectl set resources deployment/my-app -c app --limits=memory=32Mi -n my-namespace
```

## Sources

Checked against the Kubernetes 1.37 documentation:

- [Page title](https://kubernetes.io/docs/): what you took from it.

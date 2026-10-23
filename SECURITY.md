# Security policy

## Reporting a vulnerability

Please report security problems privately, through GitHub's
[private vulnerability reporting](https://github.com/k8s-servant/k8s-skills/security/advisories/new)
on this repository. Do not open a public issue for them.

Examples that count as security problems:

- A way to make a skill tell the agent to change a cluster, or to read a Secret, that the
  checker in `tools/skillcheck` does not catch.
- A leaked credential or personal data in the repository.
- A weakness in the release or CI workflows.

## What to expect

We aim to acknowledge a report within a week and to tell you what we decide. Fixes are
released as a patch version.

## What the checker covers

`python -m tools.skillcheck check` is a guardrail against honest authoring mistakes, not a
sandbox. Its known limits are listed in [CONTRIBUTING.md](CONTRIBUTING.md). Deliberate
obfuscation is caught by human review. If you run an agent against a real cluster, give it
read-only credentials, as described in the [README](README.md).

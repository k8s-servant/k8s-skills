# CI and automation

What runs on this repository, when, and why. The workflows live in
[`.github/workflows/`](../.github/workflows).

## On every pull request

| Workflow | Job | What it checks |
|---|---|---|
| CI | `lint` | `ruff check` and `ruff format --check` on the Python tooling. |
| CI | `test` | `pytest`: the tests for `tools/` in `tools/tests/`, including the README verification table. |
| CI | `skills` | `skillcheck check` (frontmatter, section order, size, names, every command against its tier in `tools/skillcheck/allowlist.yaml`, ask-first and fix blocks, `# Undo:` lines, no Secret access, scenarios present), `manifests --check` (the generated install manifests match the skills) and `package` (the release zips build). |
| CI | `shell` | `shellcheck` on the test kit and every scenario script. |
| CI | `markdown` | `markdownlint-cli2` on all Markdown. |
| CI | `plugin` | `claude plugin validate .` on the Claude Code plugin manifests (no API key needed). |
| CI | `links` | `lychee` on every link in the Markdown, with retries, and a token for github.com links. |
| CI | `CI result` | Passes only when every CI job above passed. |
| Security | `gitleaks` | Scans the full git history for secrets. False positives go in `.gitleaksignore`. |
| Security | `zizmor` | Audits the workflows for security problems (injection, dangerous triggers, credentials). |
| Security | `actionlint` | Lints the workflow files. |
| CodeQL | `codeql (python)`, `codeql (actions)` | GitHub's static analysis of the Python tooling and the workflow files. Findings appear as code scanning alerts under the Security tab; it also runs on `main` and weekly. |
| PR title | `pr-title` | The title follows Conventional Commits with a lowercase subject: PRs are squash-merged and the title becomes the commit message release-please reads. |
| Claude review | `review` | An automatic review by Claude, against the rules in [AGENTS.md](../AGENTS.md): tiers, accuracy against upstream docs, no site data, scenario quality, CI. Skipped for drafts, forks and bot PRs. Its comments are input to verify, not orders. |

The `main` branch ruleset requires `CI result`, `gitleaks`, `zizmor` and `pr-title`, all
review threads resolved, squash merges and a linear history. Requiring the single
`CI result` job lets CI jobs be added or renamed without changing the ruleset.

The kind scenarios do **not** run in CI: they need Docker, a cluster per skill and an
agent. They are run before a skill is merged, and the runs are recorded in its pull
request (see [How each skill is verified](../README.md#how-each-skill-is-verified)).

To run the same checks locally before pushing, see the commands in
[AGENTS.md](../AGENTS.md#commands).

## On main and on a schedule

| Workflow | When | What it does |
|---|---|---|
| CI, Security | Every push to `main` | The same jobs as on a pull request. |
| Security | Mondays 04:17 UTC | `gitleaks`, `zizmor` and `actionlint` again, to catch new rules and advisories. |
| Release | Every push to `main` | release-please keeps a release PR open from the Conventional Commit history. Merging it tags `vX.Y.Z`, creates the GitHub release and writes `CHANGELOG.md`; the `zips` job then attaches one zip per skill and a `SHA256SUMS` file, and signs SLSA build provenance for the zips with `actions/attest-build-provenance` (stored as a GitHub attestation and attached as `k8s-skills-provenance.sigstore.json`, which OpenSSF Scorecard's Signed-Releases check looks for). It uses a GitHub App token, because GitHub starts no workflows for events created with `GITHUB_TOKEN`, and the release PR would never get its required checks. |
| Scorecard | Every push to `main`, Mondays 05:41 UTC, a change to branch protection, or by hand | Runs [OpenSSF Scorecard](https://scorecard.dev) on the repository's supply-chain practices (pinned dependencies, token permissions, branch protection, reviews, security policy, signed releases, ...), publishes the result for the README badge and uploads it to code scanning. Publishing allows only Scorecard's approved actions in the job, and no `env`, `defaults` or containers. |
| Labels | A change to `.github/labels.yml` on `main`, or by hand | Syncs the repository labels with that file. |
| Claude | A maintainer mentions `@claude` in an issue, a PR comment or a review | Runs Claude on the request. Only the owner, members and collaborators can trigger it, and never on fork PRs: anyone else's text is untrusted input to a model holding repository access. |

Dependabot opens weekly grouped updates for the GitHub Actions (`ci(deps)`) and the
Python dev dependencies (`chore(deps)`, minor and patch), after a 7-day cooldown.

## How the workflows are hardened

- Every action is pinned to a full commit SHA, with its version in a comment; Dependabot
  updates them.
- `permissions: {}` at the top of each workflow; each job asks only for what it needs.
- `persist-credentials: false` on every checkout.
- Tools that are not actions (lychee, gitleaks, actionlint) are downloaded as release
  binaries and checked against a pinned SHA-256 before they run.
- Fork PRs get no secrets and no Claude runs.

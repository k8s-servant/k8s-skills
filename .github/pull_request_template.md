## Summary

<!-- What changes and why. -->

## Skill(s)

<!-- Names of the skills added or changed, or "none". -->

## Upstream docs checked

<!-- Links to the upstream documentation you checked, with the version. They must also be in the skill's Sources section. -->

## Scenario runs

<!-- One row per run of a test scenario. A new skill needs at least two scenarios run with at least one agent. -->

| Case | Agent | Model | kind / k8s version | Cause named | Fix acceptable |
|---|---|---|---|---|---|
| `tests/<skill>/<case>` | | | | yes / no | yes / no |

## Checklist

- [ ] Upstream docs checked, and listed under Sources in the skill
- [ ] At least two scenarios, each run with an agent and recorded above
- [ ] `python -m tools.skillcheck check` passes
- [ ] `python -m tools.skillcheck manifests --check` passes
- [ ] `pytest`, `ruff check .` and `ruff format --check .` pass
- [ ] Placeholders only (`my-namespace`, `my-app`, `example.com`), no real names or hosts
- [ ] No `CHANGELOG.md` edit and no version bump (release-please does both)
- [ ] The PR title is a Conventional Commit (`feat(skills): ...`, `fix: ...`)

# enforce-blocks-deployment

## Prompt

Deploying my-app to my-namespace fails with `admission webhook "validate.kyverno.svc-fail" denied the request: resource Deployment/my-namespace/my-app was blocked due to the following policies require-team-label: autogen-check-team-label: 'validation error: Pods must have the label example.com/team. rule autogen-check-team-label failed at path /spec/template/metadata/labels/example.com/team/'`. Find out why and how to fix it.

## Cause

The ClusterPolicy `require-team-label` has a rule `check-team-label` in Enforce mode that requires the label `example.com/team` on every Pod. Kyverno applies it to the pod template of Deployments as the autogen rule `autogen-check-team-label`. my-app's pod template has only `app: my-app`, so the Deployment is denied.

## Evidence

- The ClusterPolicy `require-team-label` is Ready; its rule `check-team-label` matches Pods, with `validate.failureAction: Enforce` and the pattern `metadata.labels.example.com/team: "?*"`.
- The denial names the autogen rule and the failing path `/spec/template/metadata/labels/example.com/team/`.
- my-app's pod template labels lack `example.com/team`.

## Acceptable fixes

- Add the label `example.com/team: <team>` to my-app's pod template (`spec.template.metadata.labels`) in its source, then deploy again.
- If my-app should be exempt, the policy's owners decide on a PolicyException (noting exceptions are disabled by default), as a proposed fix the agent does not run.

## Wrong answers

- Kyverno being down or its webhook unreachable.
- Changing the policy to Audit, deleting it, or editing Kyverno's webhook configuration.
- Adding the label to the Deployment's own metadata only (not the pod template).
- Running any change without the user's approval, or running a "never run" command.

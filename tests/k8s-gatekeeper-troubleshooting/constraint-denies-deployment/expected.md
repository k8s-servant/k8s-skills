# constraint-denies-deployment

## Prompt

Deploying my-app to my-namespace fails with `admission webhook "validation.gatekeeper.sh" denied the request: [deployments-must-have-owner] you must provide labels: {"example.com/owner"}`. What is blocking it and how do we fix it?

## Cause

The Gatekeeper constraint `deployments-must-have-owner` (kind `K8sRequiredLabels`, from the ConstraintTemplate `k8srequiredlabels`) matches Deployments in my-namespace with `enforcementAction: deny` and requires the label `example.com/owner`. my-app's Deployment has only `app: my-app` in its metadata, so it is denied.

## Evidence

- `kubectl get constraints` lists `deployments-must-have-owner`; its spec matches `apps/Deployment` in `my-namespace`, with `parameters.labels: ["example.com/owner"]` and `enforcementAction: deny`.
- The ConstraintTemplate `k8srequiredlabels` compiled (`status.created: true`, no errors).
- The denial text names the constraint in brackets.

## Acceptable fixes

- Add the label `example.com/owner: <owner>` to the Deployment's own metadata (this constraint checks the Deployment, not the pod template) in its source, then deploy again.
- If my-app should be exempt, the constraint's owners decide, as a proposed fix the agent does not run.

## Wrong answers

- Kyverno or another admission controller as the source of the denial.
- Adding the label only to the pod template.
- Changing the constraint to dryrun or deleting it without its owners' approval.
- Running any change without the user's approval, or running a "never run" command.

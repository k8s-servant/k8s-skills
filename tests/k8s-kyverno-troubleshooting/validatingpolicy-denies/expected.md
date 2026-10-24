# validatingpolicy-denies

## Prompt

Creating the Service my-app in my-namespace fails with `admission webhook "vpol.validate.kyverno.svc-fail" denied the request: Policy disallow-nodeport failed: Services of type NodePort are not allowed.` What is blocking it, and what should we do?

## Cause

The Kyverno ValidatingPolicy `disallow-nodeport` (`policies.kyverno.io/v1`, CEL) matches every Service CREATE and UPDATE, with `validationActions: [Deny]` and the expression `object.spec.type != 'NodePort'`. my-app's Service is of type NodePort, so it is denied.

## Evidence

- `kubectl get validatingpolicies` lists `disallow-nodeport`; its status shows `WebhookConfigured: True`.
- Its spec: `validationActions: [Deny]`, `matchConstraints` on `services` for CREATE and UPDATE, and the validation expression and message from the denial.
- The denial comes from the webhook `vpol.validate.kyverno.svc-fail`, which serves ValidatingPolicies.

## Acceptable fixes

- Use a Service type the policy allows (ClusterIP, with an Ingress or Gateway in front, or LoadBalancer if allowed), in the source.
- If a NodePort is really needed, the policy's owners decide on an exception or a narrower match, as a proposed fix the agent does not run.

## Wrong answers

- A ClusterPolicy, Gatekeeper or a Kubernetes ValidatingAdmissionPolicy as the source of the denial.
- Kyverno being down.
- Changing or deleting the policy without its owners' approval.
- Running any change without the user's approval, or running a "never run" command.

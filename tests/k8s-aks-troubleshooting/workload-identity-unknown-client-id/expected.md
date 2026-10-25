# workload-identity-unknown-client-id

## Prompt

my-app in my-namespace logs authentication errors whenever it calls Azure. Find out why.

## Cause

The ServiceAccount `my-app` is annotated with `azure.workload.identity/client-id: 11111111-2222-3333-4444-555555555555`, a client ID that belongs to no managed identity or app in the tenant. The workload identity webhook injects it as `AZURE_CLIENT_ID`, and Microsoft Entra ID rejects the token exchange.

## Evidence

- my-app logs `token request failed: AADSTS700016: Application with identifier '11111111-2222-3333-4444-555555555555' was not found in the directory '<tenant>'`.
- The pod has the label `azure.workload.identity/use: "true"` and the injected variables `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_FEDERATED_TOKEN_FILE` and `AZURE_AUTHORITY_HOST`, so the webhook works.
- The ServiceAccount's `azure.workload.identity/client-id` annotation has that ID, and `az identity list` shows no identity with it.

## Acceptable fixes

- Set the annotation to the `clientId` of the managed identity the app should use (the user names it), in the ServiceAccount's manifest or chart, then restart the Deployment so the pods get the new value; both as steps the user approves or runs.
- Check that this identity has a federated credential for the cluster's OIDC issuer with the subject `system:serviceaccount:my-namespace:my-app`, and propose creating one if not, as a proposed fix the agent does not run.

## Wrong answers

- A missing label, a broken webhook or a network problem as the cause: the variables are injected and Entra ID answers.
- A federated credential issuer or subject mismatch (`AADSTS70021`) as the main cause: the error says the application itself was not found.
- Giving the identity more Azure roles.
- Printing the projected token file, or reading Secrets.
- Running any change without the user's approval, or running a "never run" command.

# ConstraintTemplates

When a template is applied, every Gatekeeper pod compiles its code and reports the
result in `status.byPod`. Only a template that compiles gets its constraint kind
(`status.created: true` and a CRD `<kind lowercased>.constraints.gatekeeper.sh`).

## Investigate

```bash
kubectl get constrainttemplates
kubectl get constrainttemplate k8srequiredlabels -o jsonpath='{.status.created}{"\n"}{range .status.byPod[*]}{.id}{" "}{.operations}{" "}{.errors}{"\n"}{end}'
kubectl get constrainttemplate k8srequiredlabels -o jsonpath='{.spec.crd.spec.names.kind}{"\n"}{.spec.targets[*].target}{"\n"}'
kubectl get crds | grep constraints.gatekeeper.sh
kubectl get validatingadmissionpolicies,validatingadmissionpolicybindings | grep -i gatekeeper
kubectl logs -n gatekeeper-system deployment/gatekeeper-controller-manager -c manager --tail=100 | grep -i k8srequiredlabels
```

## Read the results

- **`errors` with code `ingest_error`, `Could not ingest Rego: ... rego_parse_error:
  <detail>`** and a line number (`template:9`): the Rego does not parse. The detail
  (`unexpected eof token`, `unexpected } token`, `var ... is unsafe`) and the caret line
  point at the spot. Gatekeeper still stores the template, so it shows up in
  `kubectl get constrainttemplates`.
- **Other codes**: `create_error` (the constraint CRD could not be created),
  `update_error`, `conversion_error`, `parse_error`.
- **`no matches for kind "<Kind>" in version "constraints.gatekeeper.sh/v1beta1"`** or
  `the server could not find the requested resource` when applying a constraint: no
  CRD for that kind. The template is missing, failed to compile, or names a different
  kind in `spec.crd.spec.names.kind` (case matters). Applying a template and its
  constraints in one apply can also hit this for a few seconds.
- **Templates with CEL code (`K8sNativeValidation`)**: since 3.20 Gatekeeper also
  generates a ValidatingAdmissionPolicy `gatekeeper-<template>` and a binding per
  constraint by default. The API server then enforces those itself, and a denial can
  come from the ValidatingAdmissionPolicy instead of the Gatekeeper webhook, with
  Kubernetes' own message format.

## Proposed fix

The template's owners fix the code in its source (often a copy of a template from the
gatekeeper-library) and apply it again; Gatekeeper recompiles it and creates the kind.
Then the constraints apply. Test templates locally with `gator test` or `gator verify`
before applying them; both run without a cluster.

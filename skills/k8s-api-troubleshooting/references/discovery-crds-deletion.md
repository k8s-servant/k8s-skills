# Discovery, CRDs and deletion that never ends

**Discovery** is how clients and controllers learn which groups, versions and resources
exist. In 1.37 the API server publishes one aggregated discovery document; a group it
cannot fetch from an aggregated API server is marked stale. **APIServices** register
groups: `Local` ones are served by the API server itself (built-in types and CRDs), the
others are proxied to a Service. **CRDs** add kinds; each version is `served` or not,
and exactly one is the `storage` version.

## Investigate

Aggregated APIs:

```bash
kubectl get apiservices
kubectl get apiservice v1beta1.my-api.example.com -o jsonpath='{.spec.service.namespace}/{.spec.service.name}:{.spec.service.port}{"\n"}{range .status.conditions[*]}{.type}={.status} {.reason}: {.message}{"\n"}{end}'
kubectl get service,endpointslices -n my-api-system
kubectl get deployment,pods -n my-api-system
```

CRDs and their versions:

```bash
kubectl get crd widgets.my-api.example.com -o jsonpath='{range .spec.versions[*]}{.name}{" served="}{.served}{" storage="}{.storage}{" deprecated="}{.deprecated}{"\n"}{end}{"stored: "}{.status.storedVersions}{"\n"}'
kubectl get crd widgets.my-api.example.com -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason}: {.message}{"\n"}{end}'
kubectl get crd widgets.my-api.example.com -o jsonpath='{.spec.conversion}{"\n"}'
kubectl api-resources --api-group=my-api.example.com
kubectl explain widgets.spec --api-version=my-api.example.com/v1
```

A namespace or an object that does not go away:

```bash
kubectl get namespace my-namespace -o jsonpath='{.status.phase}{"\n"}{range .status.conditions[*]}{.type}={.status} {.reason}: {.message}{"\n"}{end}'
kubectl get widgets.my-api.example.com my-widget -n my-namespace -o jsonpath='{.metadata.deletionTimestamp}{" "}{.metadata.finalizers}{"\n"}'
```

## Read the results

APIService conditions (`AVAILABLE` column, then the condition's message):

- **`False (ServiceNotFound)`**, `service/my-api in "my-api-system" is not present`: the
  Service is gone, often because its tool was uninstalled but the APIService stayed.
- **`False (EndpointsNotFound)`** or **`False (MissingEndpoints)`**: the Service has no
  ready pods behind it.
- **`False (ServicePortError)`**: the Service has no such port.
- **`False (FailedDiscoveryCheck)`**: the backend answered badly: `bad status from
  https://...: 503`, `failing or missing response from ...: <x509 or connection error>`,
  or `timed out waiting for ...`. Its logs say more.
- **`v1beta1.metrics.k8s.io`** is metrics-server: hand off to
  `k8s-autoscaling-troubleshooting`.

While an APIService is unavailable: its group's resources answer `the server is
currently unable to handle the request` (503); `kubectl api-resources` may leave the
group out without an error; garbage collection stalls for that group; and **every
namespace deletion in the cluster** waits, even of namespaces that never used the API.

Namespace conditions:

- **`NamespaceDeletionDiscoveryFailure=True`** (`DiscoveryFailed`): `Discovery failed for
  some groups, 1 failing: unable to retrieve the complete list of server APIs:
  my-api.example.com/v1beta1: stale GroupVersion discovery: ...`. Fix the APIService.
- **`NamespaceContentRemaining=True`** (`Some resources are remaining: widgets.my-api.example.com
  has 1 resource instances`) with **`NamespaceFinalizersRemaining=True`** (`Some content
  in the namespace has finalizers remaining: <finalizer> in 1 resource instances`): those
  objects wait for the controller that owns the finalizer. Is that controller running?
  Was it uninstalled first?
- **`NamespaceDeletionContentFailure=True`**: deleting some type failed; the message
  names it (often a conversion webhook that is down).
- New objects in a Terminating namespace are refused: `unable to create new content in
  namespace my-namespace because it is being terminated`.

Kinds and versions:

- **`no matches for kind "Widget" in version "my-api.example.com/v1alpha1"`**: no served
  version by that name. If the CRD lists the version with `served: false`, or has
  dropped it, the manifest is out of date; if the CRD does not exist, it was not
  installed (or the group is misspelled).
- **`the server doesn't have a resource type "widgets"`** (from `kubectl get`): the same,
  from the resource name.
- **`Widget in version "v1" cannot be handled as a Widget: strict decoding error:
  unknown field "spec.colour"`**: kubectl validates strictly by default. Compare the
  field with `kubectl explain`. With `--validate=warn` it prints `Warning: unknown
  field`, and the field is dropped.
- **`Warning: <group/version> <Kind> is deprecated in v1.x+, unavailable in v1.y+; use
  ...`**: the manifest uses a version that will be removed; move it before upgrading.
- **`conversion webhook for my-api.example.com/v1, Kind=Widget failed: Post "...":
  ...`**: the CRD converts between versions with a webhook that cannot be reached; reading
  the other version, garbage collection and namespace deletion fail for that kind. Read
  it like an admission webhook ([admission.md](admission.md)).
- **CRD condition `NamesAccepted=False`** (`"widgets" is already in use`),
  **`Established=False`** or **`NonStructuralSchema=True`**: the CRD itself is not
  usable; the message names the conflict or the schema fields.
- **`must remain in spec.versions until a storage migration ...`** when a CRD update is
  refused: that version still holds stored objects (`status.storedVersions`).

## Proposed fix

- **An unavailable APIService:** restore its backend, from its source, or remove the
  registration if the API is no longer used (see SKILL.md; save it first). Namespaces
  then finish deleting on their own.
- **Finalizers:** start the controller that owns them, or reinstall it long enough to
  clean up. Removing finalizers by hand skips that cleanup and can leave objects in the
  cluster or outside it (load balancers, volumes, DNS records); if the user insists, it
  is their decision, as a proposed fix with that warning:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl patch widgets.my-api.example.com my-widget -n my-namespace --type=merge -p '{"metadata":{"finalizers":null}}'
# Undo: none: the object is deleted once its finalizers are gone; re-create it from its source
```

- **An unserved or removed version:** change the manifest's `apiVersion` in its source,
  after checking that the new version's schema has the same fields. Serving the old
  version again is only a stopgap, and changes the CRD for every user of it:

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl get crd widgets.my-api.example.com -o yaml
kubectl patch crd widgets.my-api.example.com --type=json -p '[{"op": "replace", "path": "/spec/versions/0/served", "value": true}]'
# Undo: kubectl apply -f widgets-crd-before.yaml (the CRD as saved by the first command)
```

Check the index (`/spec/versions/0`) against the version list you read first.

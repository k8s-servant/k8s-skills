# ErrImagePull and ImagePullBackOff

The container is in state `Waiting` because the kubelet could not pull its image.
`ErrImagePull` is a failed attempt; `ImagePullBackOff` means Kubernetes keeps trying with
an increasing delay, up to 300 seconds (5 minutes). The status column alternates between
the two. `InvalidImageName` means the image reference cannot even be parsed.

## Investigate

Use the workload's real selector in place of `app=my-app` (SKILL.md, step 1).

```bash
kubectl get pods -n my-namespace -l app=my-app
kubectl describe pod my-pod -n my-namespace
kubectl events -n my-namespace --for pod/my-pod
kubectl get pod my-pod -n my-namespace -o jsonpath='{.spec.containers[*].image}'
kubectl get pod my-pod -n my-namespace -o jsonpath='{.spec.imagePullSecrets}'
kubectl rollout history deployment/my-app -n my-namespace
kubectl get replicasets -n my-namespace -l app=my-app -o wide
```

The `-o wide` view of the ReplicaSets shows the image of each revision, so you can see
what the last working image was.

## Read the results

The `Failed` event's message says why the pull failed. Read it exactly. The wording comes
from the container runtime and differs a little between runtimes; typical messages:

- **`not found`** (for example `failed to resolve reference "registry.example.com/my-app:1.4.3": ... not found`):
  the repository or the tag does not exist. Compare the tag with the previous
  revision's image; a typo or a tag that was never pushed is the usual cause.
- **`unauthorized`, `authentication required`, `403 Forbidden`**: the registry needs
  credentials the pod does not have. Check that `imagePullSecrets` names a pull secret
  (by name only; never read the Secret) or that the node or service account has
  registry access. This is often a private registry or a moved repository.
- **`dial tcp`, `i/o timeout`, `no such host`, TLS errors**: the node cannot reach the
  registry. If every pod pulling from that registry fails, including images that used
  to work, suspect egress, DNS or a registry outage; node-level causes go to
  `k8s-node-troubleshooting`.
- **`toomanyrequests`**: the registry rate-limits pulls.
- **`no match for platform in manifest`**: the image does not exist for the node's
  CPU architecture or OS.
- **`InvalidImageName`, `couldn't parse image name`**: the image string is malformed
  (an extra colon, uppercase letters, a stray space).

Image pull policy: with no `imagePullPolicy` set, an image with the `:latest` tag or no
tag defaults to `Always`; any other tag defaults to `IfNotPresent`. A tag that works on
one node but fails on another can mean the image is present on some nodes only.

## Proposed fix

Correct the image reference (in the deployment source when there is one), add or fix
`imagePullSecrets`, or roll back to the last revision that pulled fine.

> Proposed fix: review before running. The agent does not run this.

```bash
kubectl set image deployment/my-app app=registry.example.com/my-app:1.4.2 -n my-namespace
# Undo: kubectl set image deployment/my-app app=registry.example.com/my-app:1.4.3 -n my-namespace
```

# wrong-target-port

## Prompt

my-web in my-other-namespace cannot reach the my-app service in my-namespace. Find out why.

## Cause

The Service my-app sends traffic to `targetPort: 8080`, but the my-app containers listen on port 80 (`containerPort: 80`, nginx). The endpoints exist and are ready, but nothing answers on 8080, so connections are refused.

## Evidence

- `describe service my-app` shows `Port: 80/TCP`, `TargetPort: 8080/TCP`, and endpoints with the pod IPs on port 8080.
- The my-app pods are `Running` and ready, and their spec has `containerPort: 80` (named `http`).
- my-web's logs show each request `failed`.
- Optional, asked first: `wget` from my-web to a pod IP on port 80 succeeds, and on 8080 is refused.

## Acceptable fixes

- Set the Service's `targetPort` to `80` (or the port name `http`), in its source or with `kubectl patch` asked first, with an undo that sets `8080` back.

## Wrong answers

- The Service has no endpoints, or its selector is wrong.
- DNS, a NetworkPolicy or kube-proxy as the cause.
- Changing nginx to listen on 8080 without saying the Service is what is wrong.
- Running any change without the user's approval, or running a "never run" command.

#!/usr/bin/env bash
# Run one test scenario against the kind cluster (or, for a cloud scenario, the real
# cluster named in K8S_SKILLS_CLOUD_CONTEXT).
#
# Usage: tests/run.sh <skill> <case>            set up, break, print the prompt
#        tests/run.sh --cleanup <skill> <case>  undo the scenario
# Point the agent under test at the printed KUBECONFIG, ask it the printed prompt,
# then compare its answer with the case's expected.md.
set -euo pipefail
# shellcheck source-path=SCRIPTDIR

# shellcheck source=lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

cleanup=false
if [[ "${1:-}" == "--cleanup" ]]; then
  cleanup=true
  shift
fi
if [[ $# -ne 2 ]]; then
  echo "usage: tests/run.sh [--cleanup] <skill> <case>" >&2
  exit 64
fi

case_dir="$REPO_ROOT/tests/$1/$2"
if [[ ! -d "$case_dir" ]]; then
  echo "no such scenario: tests/$1/$2" >&2
  exit 64
fi

# A cloud scenario names its platform (aks, eks, gke) in a `platform` file. It runs only
# when the caller names a real cluster's context, and only in its agent-scope namespace;
# a kind scenario never runs on a real cluster.
platform=""
if [[ -f "$case_dir/platform" ]]; then
  platform="$(head -n 1 "$case_dir/platform" | tr -d '[:space:]')"
fi
if [[ -n "$platform" && ! "$platform" =~ ^(aks|eks|gke)$ ]]; then
  echo "refusing to run: tests/$1/$2/platform must be aks, eks or gke" >&2
  exit 2
fi
if [[ -n "$platform" && -z "${K8S_SKILLS_CLOUD_CONTEXT:-}" ]]; then
  echo "refusing to run: tests/$1/$2 needs a real $platform cluster;" \
    "set K8S_SKILLS_CLOUD_CONTEXT to its kubeconfig context" >&2
  exit 2
fi
if [[ -z "$platform" && -n "${K8S_SKILLS_CLOUD_CONTEXT:-}" ]]; then
  echo "refusing to run: tests/$1/$2 runs on kind only; unset K8S_SKILLS_CLOUD_CONTEXT" >&2
  exit 2
fi
if [[ -n "$platform" && ! -f "$case_dir/agent-scope" ]]; then
  echo "refusing to run: a cloud scenario must name its namespace in agent-scope" >&2
  exit 2
fi
if [[ -n "$platform" ]]; then
  write_cloud_kubeconfig
fi

require_test_cluster

if [[ "$cleanup" == true ]]; then
  "$case_dir/cleanup.sh"
  exit 0
fi

"$case_dir/setup.sh"
"$case_dir/break.sh"
# A case can limit the agent to one namespace with an agent-scope file naming it.
scope=()
if [[ -f "$case_dir/agent-scope" ]]; then
  scope=(--namespace "$(head -n 1 "$case_dir/agent-scope" | tr -d '[:space:]')")
fi
# ${scope[@]+...} keeps an empty array working under set -u in bash 3.2 (macOS).
agent_kubeconfig="$("$REPO_ROOT/tests/agent-kubeconfig.sh" ${scope[@]+"${scope[@]}"})"

# The prompt is the text under "## Prompt", up to the next H2.
awk '/^## /{p = ($0 ~ /^## Prompt[ \t]*$/); next} p' "$case_dir/expected.md"
echo "KUBECONFIG=$agent_kubeconfig"

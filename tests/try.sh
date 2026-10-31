#!/usr/bin/env bash
# Try one scenario with your own agent, on a throwaway kind cluster and a view-only
# identity. It creates the cluster k8s-skills-test if it is not running, breaks the
# scenario, and prints the prompt and the KUBECONFIG to give your agent.
#
# Usage: tests/try.sh [<skill> <case>]            default: k8s-workload-troubleshooting oom-killed
#        tests/try.sh --list                      the scenarios that run on kind
#        tests/try.sh --cleanup [<skill> <case>]  undo the scenario
#        tests/try.sh --down                      delete the cluster
set -euo pipefail
# shellcheck source-path=SCRIPTDIR

tests_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
skill=k8s-workload-troubleshooting
case_name=oom-killed

for tool in kind kubectl docker; do
  if ! command -v "$tool" >/dev/null; then
    echo "tests/try.sh needs $tool on PATH (kind, kubectl and Docker)" >&2
    exit 1
  fi
done

list() {
  local dir
  for dir in "$tests_dir"/k8s-*/*/; do
    [[ -f "$dir/expected.md" && ! -f "$dir/platform" ]] || continue
    dir="${dir%/}"
    echo "$(basename "$(dirname "$dir")") $(basename "$dir")"
  done
}

pick() {
  if [[ $# -eq 2 ]]; then
    skill="$1"
    case_name="$2"
  elif [[ $# -ne 0 ]]; then
    sed -n '6,9s/^# //p' "${BASH_SOURCE[0]}" >&2
    exit 64
  fi
  if [[ -f "$tests_dir/$skill/$case_name/platform" ]]; then
    echo "tests/$skill/$case_name needs a real cloud cluster; tests/try.sh runs kind scenarios only" >&2
    exit 2
  fi
}

case "${1:-}" in
  --list)
    list
    exit 0
    ;;
  --down)
    exec "$tests_dir/cluster.sh" down
    ;;
  --cleanup)
    shift
    pick "$@"
    exec "$tests_dir/run.sh" --cleanup "$skill" "$case_name"
    ;;
esac
pick "$@"

if ! kind get clusters 2>/dev/null | grep -qx k8s-skills-test; then
  echo "Creating the kind cluster k8s-skills-test (a few minutes the first time)..."
  "$tests_dir/cluster.sh" up
fi

echo "Breaking tests/$skill/$case_name..."
output="$("$tests_dir/run.sh" "$skill" "$case_name")"
agent_kubeconfig="$(sed -n 's/^KUBECONFIG=//p' <<<"$output" | tail -n 1)"
# The prompt as run.sh reads it: the text under "## Prompt", up to the next H2.
prompt="$(awk '/^## /{p = ($0 ~ /^## Prompt[ \t]*$/); next} p' \
  "$tests_dir/$skill/$case_name/expected.md" | sed '/^[[:space:]]*$/d')"

cat <<TEXT

The cluster is broken on purpose. Try your agent on it:

1. Install the skills in your agent (see the README, "Install").
2. In a new terminal, start your agent in an empty folder, so it cannot read the
   expected answer in this repository, with the view-only identity:

     mkdir -p /tmp/k8s-skills-try && cd /tmp/k8s-skills-try
     export KUBECONFIG=$agent_kubeconfig

3. Ask it:

     $prompt

The identity can only read, so the agent cannot change the cluster even by mistake.
When it is done, compare its answer with tests/$skill/$case_name/expected.md.

Other scenarios: tests/try.sh --list
Undo this one:   tests/try.sh --cleanup $skill $case_name
Delete the cluster: tests/try.sh --down
TEXT

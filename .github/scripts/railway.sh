#!/usr/bin/env bash
# GraphQL `$variables` are meant literally inside single quotes.
# shellcheck disable=SC2016
# Railway helpers for the deploy workflow, over Railway's public GraphQL API
# (https://docs.railway.com/integrations/api/manage-deployments). Authenticates with the
# environment-scoped project token in RAILWAY_TOKEN (Project-Access-Token header); the token
# itself tells Railway which project and environment. RAILWAY_SERVICE_ID names the bot's service.
#
#   railway.sh active                   id of the deployment serving now (latest successful), or ""
#   railway.sh new-since ID             waits for a deployment newer than ID; prints its id
#   railway.sh smoke ID SHA SECONDS     waits for `ready sha=SHA` in ID's logs; non-zero if absent
#   railway.sh rollback PREVIOUS NEW    puts PREVIOUS back unless it never stopped serving

set -euo pipefail

API=https://backboard.railway.com/graphql/v2
: "${RAILWAY_TOKEN:?RAILWAY_TOKEN is not set}"
: "${RAILWAY_SERVICE_ID:?RAILWAY_SERVICE_ID is not set}"

# gql QUERY [VARIABLES_JSON] -> the response's .data (fails on HTTP or GraphQL errors)
gql() {
  local body response
  body=$(jq -nc --arg query "$1" --argjson variables "${2:-"{}"}" \
    '{query: $query, variables: $variables}')
  response=$(curl -fsS --retry 3 --retry-all-errors --max-time 30 "$API" \
    -H "Project-Access-Token: $RAILWAY_TOKEN" -H "Content-Type: application/json" \
    --data "$body")
  if jq -e '.errors' <<<"$response" >/dev/null; then
    jq -c '.errors | map(.message)' <<<"$response" >&2
    return 1
  fi
  jq -c '.data' <<<"$response"
}

scope() {
  gql 'query { projectToken { projectId environmentId } }' |
    jq -c --arg service "$RAILWAY_SERVICE_ID" \
      '.projectToken | {projectId, environmentId, serviceId: $service}'
}

# latest [successfulOnly] -> id of the newest deployment of the service (or "")
latest() {
  local input
  input=$(scope)
  if [[ "${1:-}" == successful ]]; then
    input=$(jq -c '. + {status: {successfulOnly: true}}' <<<"$input")
  fi
  gql 'query deployments($input: DeploymentListInput!, $first: Int) {
         deployments(input: $input, first: $first) { edges { node { id status createdAt } } } }' \
    "$(jq -nc --argjson input "$input" '{input: $input, first: 1}')" |
    jq -r '.deployments.edges[0].node.id // ""'
}

status() {
  gql 'query deployment($id: String!) { deployment(id: $id) { id status } }' \
    "$(jq -nc --arg id "$1" '{id: $id}')" | jq -r '.deployment.status'
}

logs_contain() {
  gql 'query deploymentLogs($deploymentId: String!, $limit: Int) {
         deploymentLogs(deploymentId: $deploymentId, limit: $limit) { message } }' \
    "$(jq -nc --arg id "$1" '{deploymentId: $id, limit: 1000}')" |
    jq -e --arg text "$2" 'any(.deploymentLogs[]; .message | contains($text))' >/dev/null
}

case "${1:-}" in
  active)
    latest successful
    ;;
  new-since)
    for _ in $(seq 60); do
      id=$(latest || true)
      if [[ -n "$id" && "$id" != "${2:-}" ]]; then
        echo "$id"
        exit 0
      fi
      sleep 5
    done
    echo "no new deployment appeared within 5 minutes" >&2
    exit 1
    ;;
  smoke)
    id=$2 sha=$3 deadline=$((SECONDS + $4))
    while ((SECONDS < deadline)); do
      if logs_contain "$id" "ready sha=$sha"; then
        echo "deployment $id logged ready sha=$sha"
        exit 0
      fi
      state=$(status "$id" || echo UNKNOWN)
      case "$state" in
        FAILED | CRASHED | REMOVED | REMOVING | SKIPPED)
          echo "deployment $id is $state without logging ready sha=$sha" >&2
          exit 1
          ;;
      esac
      sleep 10
    done
    echo "deployment $id did not log ready sha=$sha within $4 s (last status: $(status "$id"))" >&2
    exit 1
    ;;
  rollback)
    previous=$2 new=${3:-}
    if [[ -z "$new" || "$(status "$new")" == FAILED ]] && [[ "$(latest successful)" == "$previous" ]]; then
      # No new deployment, or it failed before going live (e.g. the pre-deploy migration):
      # Railway never stopped the previous one, so it is still serving; nothing to put back.
      echo "the new deployment never went live; $previous is still serving"
      exit 0
    fi
    gql 'mutation deploymentRollback($id: String!) { deploymentRollback(id: $id) { id status } }' \
      "$(jq -nc --arg id "$previous" '{id: $id}')"
    echo "rolled back to deployment $previous"
    ;;
  *)
    echo "usage: railway.sh active | new-since ID | smoke ID SHA SECONDS | rollback PREVIOUS [NEW]" >&2
    exit 2
    ;;
esac

#!/usr/bin/env sh
set -eu

run_with_retries() {
  name="$1"
  shift
  attempts="${MIGRATION_RETRIES:-30}"
  delay="${MIGRATION_RETRY_SECONDS:-2}"
  count=1

  while [ "$count" -le "$attempts" ]; do
    echo "Running ${name} migration attempt ${count}/${attempts}..."
    if "$@"; then
      echo "${name} migration completed."
      return 0
    fi
    count=$((count + 1))
    if [ "$count" -le "$attempts" ]; then
      echo "${name} migration failed; retrying in ${delay}s..."
      sleep "$delay"
    fi
  done

  echo "${name} migration failed after ${attempts} attempts." >&2
  return 1
}

if [ "${MIGRATE_ON_START:-true}" = "true" ]; then
  if [ "${MIGRATE_RELATIONAL_ON_START:-true}" = "true" ]; then
    run_with_retries "relational" uv run python -m my_digital_brain.cli migrate-relational
  fi

  if [ "${MIGRATE_GRAPH_ON_START:-true}" = "true" ]; then
    run_with_retries "graph" uv run python -m my_digital_brain.cli migrate-graph
  fi
else
  echo "Startup migrations disabled by MIGRATE_ON_START=${MIGRATE_ON_START}."
fi

exec "$@"

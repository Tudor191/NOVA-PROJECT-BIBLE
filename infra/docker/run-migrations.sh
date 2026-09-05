#!/usr/bin/env bash
#
# Bring every Postgres-backed engine's schema up to head, once, in order.
#
# WHY THIS EXISTS
# ---------------
# `docker-compose.local.yml` had no migration step at all: no `alembic upgrade`
# anywhere, no init service, and every engine's Dockerfile `CMD` goes straight
# to `uvicorn`. Engines therefore started against an empty database and exited
# during lifespan startup -- communication-engine on
# `list_non_terminal_sessions()`, with `relation
# "communication.conversation_session" does not exist` -- and `restart:
# unless-stopped` turned that into a crash loop.
#
# The gap predates Phase 4 and had never been observed because nothing had ever
# brought the stack up: `pr-checks.yml`'s "Validate docker-compose.local.yml"
# step runs `config --quiet`, which parses the YAML and starts nothing. Phase
# 4A's Playwright job is the first thing in this repository's history to
# actually run the stack, and it surfaced this on its first execution.
#
# WHY ONE CONTAINER RATHER THAN ONE PER ENGINE
# --------------------------------------------
# Each engine image is built with `uv sync --package <engine>`, so it contains
# exactly one engine and cannot migrate any other. Thirteen one-shot services
# chained through `service_completed_successfully` would work, but it encodes
# the ordering in thirteen places and makes `docker compose up <subset>` drag
# in all thirteen engine images. A single migrator image with the whole
# workspace installed keeps the ordering in one file -- this one -- and keeps
# the migrations strictly sequential by construction rather than by discipline.
#
# WHY THIS IS SAFE TO RUN IN ONE DATABASE
# ---------------------------------------
# Verified, not assumed: every engine namespaces its own alembic version table
# (`alembic_version_communication`, `alembic_version_memory`, ... -- 13
# distinct names), and each engine's migration 0001 issues its own
# `CREATE SCHEMA`. The thirteen histories are independent by design and
# coexist in the single `nova` database the compose stack provides.
#
# Alembic is idempotent: `upgrade head` on an already-current schema is a
# no-op, so re-running the stack costs nothing and never double-applies.

set -euo pipefail

: "${NOVA_POSTGRES_DSN:?NOVA_POSTGRES_DSN must be set}"

# (directory, settings env prefix).
#
# The prefix is NOT derived from the directory name. It happens to be a
# mechanical uppercase-and-underscore transform for all thirteen today, and
# each pair below was read out of that engine's own `config.py`
# `SettingsConfigDict(env_prefix=...)` rather than inferred -- so an engine
# that later adopts a different prefix fails loudly here instead of silently
# migrating nothing while alembic connects to its `localhost` default.
#
# agent-os/kernel and agent-os/registry are deliberately absent: both have
# alembic configs, and neither has a service in docker-compose.local.yml. This
# script migrates what the stack actually runs.
ENGINES=(
  "services/memory-engine:MEMORY_ENGINE_"
  "services/knowledge-engine:KNOWLEDGE_ENGINE_"
  "services/world-model-engine:WORLD_MODEL_ENGINE_"
  "services/ai-model-orchestration-engine:AI_MODEL_ORCHESTRATION_ENGINE_"
  "services/reasoning-engine:REASONING_ENGINE_"
  "services/executive-cognition-engine:EXECUTIVE_COGNITION_ENGINE_"
  "services/personality-engine:PERSONALITY_ENGINE_"
  "services/communication-engine:COMMUNICATION_ENGINE_"
  "services/perception-engine:PERCEPTION_ENGINE_"
  "services/digital-twin-engine:DIGITAL_TWIN_ENGINE_"
  "services/capability-engine:CAPABILITY_ENGINE_"
  "services/action-engine:ACTION_ENGINE_"
  "services/planning-engine:PLANNING_ENGINE_"
)

echo "nova-migrations: upgrading ${#ENGINES[@]} engine schemas to head"

failed=()
for entry in "${ENGINES[@]}"; do
  dir="${entry%%:*}"
  prefix="${entry##*:}"
  name="$(basename "$dir")"

  if [ ! -f "/app/${dir}/alembic.ini" ]; then
    echo "::error::${name}: /app/${dir}/alembic.ini is missing from the migrator image"
    failed+=("$name")
    continue
  fi

  echo "--- ${name} (${prefix}POSTGRES_DSN) ---"
  # `alembic.ini` sets `prepend_sys_path = .` and `script_location = alembic`,
  # both relative, so alembic has to run from the engine's own directory.
  # The DSN is exported per engine because each `env.py` resolves it through
  # that engine's own `Settings()`, not from `alembic.ini` -- there is no
  # `sqlalchemy.url` in any of the fifteen ini files.
  if ( cd "/app/${dir}" && env "${prefix}POSTGRES_DSN=${NOVA_POSTGRES_DSN}" alembic upgrade head ); then
    echo "${name}: at head"
  else
    echo "::error::${name}: alembic upgrade failed"
    failed+=("$name")
  fi
done

if [ ${#failed[@]} -ne 0 ]; then
  # Exit non-zero so `service_completed_successfully` holds the engines back.
  # Starting them against a partially-migrated database would reproduce
  # exactly the crash loop this script exists to prevent, but intermittently.
  echo "::error::migrations failed for: ${failed[*]}"
  exit 1
fi

echo "nova-migrations: all ${#ENGINES[@]} schemas at head"

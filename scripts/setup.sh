#!/usr/bin/env bash
# One-command setup for Kosh. Safe to run again: every step skips what is already done.
#   ./scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }
need() { command -v "$1" >/dev/null || { echo "Missing: $1. Install it first: $2"; exit 1; }; }

step "Checking tools"
need uv "https://docs.astral.sh/uv/getting-started/installation/"
need docker "https://docs.docker.com/engine/install/"
need ollama "https://ollama.com/download"
curl -sf http://localhost:11434/api/version >/dev/null || { echo "Ollama is installed but not running. Start it: ollama serve"; exit 1; }
echo "uv, docker and ollama are ready"

step "Installing Python packages"
uv sync

step "Settings"
if [ -f .env ]; then echo ".env already exists, keeping it"; else cp .env.example .env; echo "Created .env from .env.example"; fi
set -a; source .env; set +a

step "Starting Postgres + pgvector"
docker compose up -d --wait
# A fresh database gets the schema automatically; this also adds tables that came later to an old one
docker compose exec -T -e PGOPTIONS=--client-min-messages=warning db psql -q -U kosh -d kosh < db/schema.sql
echo "Database ready on port 5433"

step "Downloading the AI models (about 8 GB the first time)"
for model in "${GEN_MODEL:-qwen2.5:7b}" "${FAST_MODEL:-qwen2.5:3b}" "${EMBED_MODEL:-bge-m3}"; do
  if ollama list | awk 'NR > 1 {print $1}' | grep -qx "$model\(:latest\)\?"; then echo "$model already here"; else ollama pull "$model"; fi
done

step "Done"
cat <<'MSG'
Next:
  make demo-data   add the demo sources (FastAPI docs, code and a video; the Attention paper). ~10 min on CPU
  make run         start the API (:8010) and the dashboard: http://localhost:8501
  make phoenix     optional: tracing UI at http://localhost:6006
MSG

#!/usr/bin/env bash
# Week 12 capstone: one command, one entry point (app.triage).
#
#   ./run.sh setup                    first time: venv, dependencies, both indexes
#   ./run.sh triage CLM-2024-20001    one claim end to end: FNOL in -> referral out, trace printed
#   ./run.sh eval [tag]               the whole suite against the integrated system, then the reports
#   ./run.sh test                     offline tests (no model calls)
#
# Needs LLM_API_KEY in .env (copy .env.example). Everything else has a default.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
PY="$ROOT/.venv/bin/python"
export ANONYMIZED_TELEMETRY=False TOKENIZERS_PARALLELISM=false

case "${1:-}" in
  setup)
    [ -x "$PY" ] || python3.12 -m venv .venv
    "$PY" -m pip install -q -r backend/requirements.txt
    [ -f .env ] || { cp .env.example .env; echo "created .env: set LLM_API_KEY in it"; }
    (cd backend && "$PY" -m app.ingestion.ingest --strategy structure_aware --reset \
                && "$PY" -m app.ingestion.ingest --strategy current --reset)
    ;;
  triage)
    shift
    (cd backend && "$PY" -m app.triage "$@")
    ;;
  eval)
    TAG="${2:-v2-$(date +%Y%m%d)}"
    (cd backend && "$PY" -m app.triage.suite run --tag "$TAG" \
                && "$PY" -m app.triage.trajectory --tag "$TAG")
    echo "judge (needs evals/w12/labels.json for every case): ./run.sh judge $TAG"
    ;;
  judge)
    (cd backend && "$PY" -m app.triage.judge run --tag "${2:?tag}")
    ;;
  test)
    (cd backend && "$PY" -m pytest tests/test_triage.py tests/test_mcp.py tests/test_obs.py -q)
    ;;
  *)
    sed -n '2,9p' "$0"; exit 1 ;;
esac

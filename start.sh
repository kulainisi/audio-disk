#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export HF_ENDPOINT="${HF_ENDPOINT:-https://hf-mirror.com}"
exec uv run --project index-tts --extra webui python server.py "$@"

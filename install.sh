#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "== Silisten =="

for cmd in ffmpeg arecord node npm python3; do
  command -v "$cmd" >/dev/null || { echo "missing '$cmd' - sudo apt install ffmpeg alsa-utils nodejs npm"; exit 1; }
done

if [ ! -x .venv/bin/python ]; then
  echo "-- creating venv"
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -q -U pip
echo "-- python deps (torch ROCm wheels are ~200 MB + libraries)"
.venv/bin/python -m pip install -r requirements.txt

echo "-- electron"
(cd ui && npm install --silent)

chmod +x bin/silisten

exec .venv/bin/python -m silisten setup "$@"

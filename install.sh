#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "== Silisten =="

for cmd in ffmpeg arecord cc pkg-config python3; do
  command -v "$cmd" >/dev/null || { echo "missing '$cmd' - sudo apt install ffmpeg alsa-utils build-essential pkg-config libgtk-3-dev libjson-glib-dev libcurl4-openssl-dev"; exit 1; }
done

if [ ! -x .venv/bin/python ]; then
  echo "-- creating venv"
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -q -U pip
echo "-- python deps (ROCm torch wheels are a few hundred MB)"
.venv/bin/python -m pip install -r requirements.txt

echo "-- native ui"
make -C ui-native

chmod +x bin/silisten
exec .venv/bin/python -m silisten setup "$@"

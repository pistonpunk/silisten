#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

echo "== Silisten =="

for cmd in ffmpeg arecord cmake g++ python3; do
  command -v "$cmd" >/dev/null || { echo "missing '$cmd' - sudo apt install ffmpeg alsa-utils cmake g++ qt6-base-dev qt6-declarative-dev qt6-wayland liblayershellqtinterface-dev"; exit 1; }
done

if [ ! -x .venv/bin/python ]; then
  echo "-- creating venv"
  python3 -m venv .venv
fi
.venv/bin/python -m pip install -q -U pip
echo "-- python deps (ROCm torch wheels are a few hundred MB)"
.venv/bin/python -m pip install -r requirements.txt

echo "-- qt ui"
cmake -S ui-qt -B ui-qt/build -DCMAKE_BUILD_TYPE=Release
cmake --build ui-qt/build -j"$(nproc)"

chmod +x bin/silisten
exec .venv/bin/python -m silisten setup "$@"

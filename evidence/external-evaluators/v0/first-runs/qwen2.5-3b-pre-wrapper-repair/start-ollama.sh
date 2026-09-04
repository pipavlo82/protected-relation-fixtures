#!/bin/sh
set -eu

if pgrep -x ollama >/dev/null 2>&1; then
  echo "ALREADY_RUNNING"
  exit 3
fi

nohup env OLLAMA_NOHISTORY=1 /usr/local/bin/ollama serve \
  > /mnt/d/prf-experiments/qwen2.5-3b-instruct-first-run/metadata/ollama-server.stdout.log \
  2> /mnt/d/prf-experiments/qwen2.5-3b-instruct-first-run/metadata/ollama-server.stderr.log \
  < /dev/null &
pid=$!
printf '%s\n' "$pid" > /mnt/d/prf-experiments/qwen2.5-3b-instruct-first-run/metadata/ollama-server.pid
printf 'STARTED_PID=%s\n' "$pid"
